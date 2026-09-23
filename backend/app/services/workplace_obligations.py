"""Paginated workplace obligation feed built from existing production records.

The feed is intentionally read-only.  It does not duplicate or close source
records; every row keeps the source entity identity so a completed historical
record and its next renewal can coexist.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from math import ceil

from sqlalchemy import func, inspect as sa_inspect, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AnnualPlanItem,
    AnnualPlanStatus,
    AssignmentStatus,
    Branch,
    ChemicalProduct,
    DocumentCategory,
    DocumentRecord,
    DrillRecord,
    EmergencyPlan,
    HealthRecord,
    IncidentDof,
    IncidentEvent,
    OhsCommitteeMeeting,
    PeriodicControl,
    PpeAssignment,
    PpeInventoryItem,
    RiskAssessment,
    RiskDof,
    TrainingSession,
    TrainingStatus,
    WorkplaceAssignment,
    WorkplaceMeasurement,
)
from app.models.remote_training import RemoteTrainingAssignment
from app.services.capa_board import incident_dof_completed
from app.services.risk_validity import add_years, build_validity


CATEGORY_LABELS = {
    "risk": "Risk değerlendirmesi",
    "training": "Eğitim",
    "ppe": "KKD",
    "sds": "SDS / PKD",
    "drill": "Tatbikat",
    "periodic_control": "Periyodik kontrol",
    "measurement": "Ortam ölçümü",
    "committee": "İSG kurulu",
    "incident": "Olay / SGK bildirimi",
    "capa": "DÖF",
    "document": "Doküman",
    "emergency_plan": "Acil durum planı",
    "annual_plan": "Yıllık plan",
    "health": "Sağlık gözetimi",
    "assignment": "İSG görevlendirmesi",
}

STATUS_LABELS = {
    "overdue": "Gecikmiş",
    "very_soon": "Çok Yakın",
    "approaching": "Yaklaşıyor",
    "scheduled": "İleri Tarihli",
    "completed": "Tamamlandı",
}

STATUS_ORDER = {
    "overdue": 0,
    "very_soon": 1,
    "approaching": 2,
    "scheduled": 3,
    "completed": 4,
}


def _as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else None


def _earliest(*values) -> date | None:
    dates = [candidate for candidate in (_as_date(value) for value in values) if candidate]
    return min(dates) if dates else None


def _status_for(due_date: date, *, today: date, completed: bool) -> tuple[str, int]:
    days_left = (due_date - today).days
    if completed:
        return "completed", days_left
    if days_left < 0:
        return "overdue", days_left
    if days_left <= 7:
        return "very_soon", days_left
    if days_left <= 30:
        return "approaching", days_left
    return "scheduled", days_left


def _obligation(
    *,
    company_id: int,
    category: str,
    source: str,
    title: str,
    due_date: date | datetime | None,
    module: str,
    entity_type: str,
    responsible_role: str,
    today: date,
    record_id: int | None = None,
    branch_id: int | None = None,
    completed: bool = False,
    occurrence: str = "deadline",
    detail: str | None = None,
) -> dict | None:
    normalized_due = _as_date(due_date)
    if normalized_due is None:
        return None
    status, days_left = _status_for(normalized_due, today=today, completed=completed)
    identity = record_id if record_id is not None else "company"
    key = f"{entity_type}:{identity}:{occurrence}:{normalized_due.isoformat()}"
    return {
        "key": key,
        "company_id": company_id,
        "branch_id": branch_id,
        "branch_name": None,
        "category": category,
        "category_label": CATEGORY_LABELS[category],
        "source": source,
        "title": title,
        "detail": detail,
        "due_date": normalized_due.isoformat(),
        "days_left": days_left,
        "status": status,
        "status_label": STATUS_LABELS[status],
        "responsible_role": responsible_role,
        "completed": completed,
        "occurrence": occurrence,
        "target": {
            "company_id": company_id,
            "module": module,
            "entity_type": entity_type,
            "record_id": record_id,
        },
    }


def _append(rows: list[dict], **kwargs) -> None:
    item = _obligation(**kwargs)
    if item is not None:
        rows.append(item)


def collect_workplace_obligations(db: Session, company, *, today: date | None = None) -> list[dict]:
    """Collect every dated obligation without an arbitrary row limit."""
    today = today or date.today()
    cid = int(company.id)
    rows: list[dict] = []

    risk_rows = list(
        db.scalars(select(RiskAssessment).where(RiskAssessment.company_id == cid)).all()
    )
    risk_by_id = {int(row.id): row for row in risk_rows}
    first_risk_created = min(
        (_as_date(row.created_at) for row in risk_rows if _as_date(row.created_at)),
        default=None,
    )
    risk_validity = build_validity(
        hazard_class=company.hazard_class,
        assessment_date=company.risk_assessment_date,
        fallback_date=first_risk_created,
        method_code=getattr(company, "risk_method", None),
        today=today,
    )
    valid_until = risk_validity.get("valid_until")
    if valid_until:
        _append(
            rows,
            company_id=cid,
            category="risk",
            source="Risk Değerlendirmesi",
            title="Risk değerlendirmesi yenileme tarihi",
            due_date=date.fromisoformat(valid_until),
            module="risk",
            entity_type="risk_assessment_document",
            responsible_role="İş Güvenliği Uzmanı / İşveren",
            today=today,
            occurrence="renewal",
            detail=risk_validity.get("message"),
        )

    for risk in risk_rows:
        if risk.status == "Açık" and risk.term_date:
            _append(
                rows,
                company_id=cid,
                branch_id=risk.branch_id,
                category="risk",
                source="Risk",
                title=f"Risk termin tarihi ({risk.risk_code})",
                due_date=risk.term_date,
                module="risk",
                entity_type="risk_assessment",
                record_id=risk.id,
                responsible_role="İş Güvenliği Uzmanı",
                today=today,
                detail=risk.risk_definition,
            )

    for dof in db.scalars(select(RiskDof).where(RiskDof.risk_id.in_(list(risk_by_id) or [-1]))).all():
        risk = risk_by_id.get(int(dof.risk_id))
        if dof.is_completed:
            _append(
                rows,
                company_id=cid,
                branch_id=getattr(risk, "branch_id", None),
                category="capa",
                source="DÖF",
                title=f"Risk DÖF ({dof.dof_code})",
                due_date=dof.completion_date or dof.term_date,
                module="capa",
                entity_type="risk_dof",
                record_id=dof.id,
                responsible_role=dof.responsible_person or "DÖF sorumlusu",
                today=today,
                completed=True,
                occurrence="completion",
                detail=dof.description,
            )
        elif dof.term_date:
            _append(
                rows,
                company_id=cid,
                branch_id=getattr(risk, "branch_id", None),
                category="capa",
                source="DÖF",
                title=f"Risk DÖF termini ({dof.dof_code})",
                due_date=dof.term_date,
                module="capa",
                entity_type="risk_dof",
                record_id=dof.id,
                responsible_role=dof.responsible_person or "DÖF sorumlusu",
                today=today,
                detail=dof.description,
            )

    training_rows = list(
        db.scalars(
            select(TrainingSession).where(
                TrainingSession.company_id == cid,
                TrainingSession.archived_at.is_(None),
                TrainingSession.status != TrainingStatus.CANCELLED,
            )
        ).all()
    )
    for training in training_rows:
        if training.status == TrainingStatus.PLANNED:
            _append(
                rows,
                company_id=cid,
                branch_id=training.branch_id,
                category="training",
                source="Planlı Eğitim",
                title=training.title,
                due_date=training.start_date,
                module="personnel_training_records",
                entity_type="training_session",
                record_id=training.id,
                responsible_role="İş Güvenliği Uzmanı / İşyeri Hekimi",
                today=today,
            )
        if training.status == TrainingStatus.COMPLETED:
            _append(
                rows,
                company_id=cid,
                branch_id=training.branch_id,
                category="training",
                source="Eğitim",
                title=training.title,
                due_date=training.end_date or training.start_date,
                module="personnel_training_records",
                entity_type="training_session",
                record_id=training.id,
                responsible_role="İş Güvenliği Uzmanı / İşyeri Hekimi",
                today=today,
                completed=True,
                occurrence="completion",
            )
            if training.next_training_date:
                _append(
                    rows,
                    company_id=cid,
                    branch_id=training.branch_id,
                    category="training",
                    source="Eğitim Yenileme",
                    title=training.title,
                    due_date=training.next_training_date,
                    module="personnel_training_records",
                    entity_type="training_session",
                    record_id=training.id,
                    responsible_role="İş Güvenliği Uzmanı / İşyeri Hekimi",
                    today=today,
                    occurrence="renewal",
                )

    if sa_inspect(db.get_bind()).has_table(RemoteTrainingAssignment.__tablename__):
        remote_rows = list(
            db.scalars(
                select(RemoteTrainingAssignment).where(RemoteTrainingAssignment.company_id == cid)
            ).all()
        )
        for assignment in remote_rows:
            is_completed = assignment.status == "completed"
            if is_completed:
                due = assignment.completed_at or assignment.due_date
            elif assignment.status == "revoked":
                continue
            else:
                due = assignment.due_date
            _append(
                rows,
                company_id=cid,
                branch_id=assignment.branch_id,
                category="training",
                source="Uzaktan Eğitim",
                title=f"Çalışan eğitim görevi #{assignment.id}",
                due_date=due,
                module="remote_training",
                entity_type="remote_training_assignment",
                record_id=assignment.id,
                responsible_role="İşyeri yetkilisi / İnsan Kaynakları",
                today=today,
                completed=is_completed,
                occurrence="completion" if is_completed else "deadline",
            )

    ppe_assignments = db.scalars(
        select(PpeAssignment).where(
            PpeAssignment.company_id == cid,
            PpeAssignment.deleted_at.is_(None),
            PpeAssignment.status.in_(("teslim", "yenilenecek")),
        )
    ).all()
    for assignment in ppe_assignments:
        _append(
            rows,
            company_id=cid,
            branch_id=assignment.branch_id,
            category="ppe",
            source="KKD Değişim",
            title=assignment.item_type,
            due_date=_earliest(assignment.renewal_date, assignment.expiry_date),
            module="ppe",
            entity_type="ppe_assignment",
            record_id=assignment.id,
            responsible_role="İşyeri yetkilisi / KKD sorumlusu",
            today=today,
            occurrence="renewal",
        )
    for item in db.scalars(
        select(PpeInventoryItem).where(
            PpeInventoryItem.company_id == cid,
            PpeInventoryItem.is_active.is_(True),
        )
    ).all():
        _append(
            rows,
            company_id=cid,
            branch_id=item.branch_id,
            category="ppe",
            source="KKD Stok",
            title=item.item_type,
            due_date=_earliest(item.renewal_date, item.expiry_date),
            module="ppe",
            entity_type="ppe_inventory_item",
            record_id=item.id,
            responsible_role="İşyeri yetkilisi / Depo sorumlusu",
            today=today,
            occurrence="renewal",
        )

    for product in db.scalars(
        select(ChemicalProduct).where(
            ChemicalProduct.company_id == cid,
            ChemicalProduct.is_active.is_(True),
        )
    ).all():
        _append(
            rows,
            company_id=cid,
            branch_id=product.branch_id,
            category="sds",
            source="SDS / PKD",
            title=product.product_name,
            due_date=product.next_review_date,
            module="sds",
            entity_type="chemical_product",
            record_id=product.id,
            responsible_role="İşveren / İş Güvenliği Uzmanı",
            today=today,
            occurrence="review",
            detail="SDS belgesi eksik." if not product.has_sds_file else None,
        )

    drills = list(
        db.scalars(
            select(DrillRecord).where(
                DrillRecord.company_id == cid,
                DrillRecord.is_active.is_(True),
                DrillRecord.status != "iptal",
            )
        ).all()
    )
    planned_drills = [row for row in drills if row.status == "planlandi"]
    completed_drills = [row for row in drills if row.status == "yapildi"]
    for drill in planned_drills:
        _append(
            rows,
            company_id=cid,
            category="drill",
            source="Tatbikat",
            title=drill.drill_type,
            due_date=drill.drill_date,
            module="tatbikat",
            entity_type="drill_record",
            record_id=drill.id,
            responsible_role=drill.responsible or "İş Güvenliği Uzmanı / İşveren",
            today=today,
        )
    for drill in completed_drills:
        _append(
            rows,
            company_id=cid,
            category="drill",
            source="Tatbikat",
            title=drill.drill_type,
            due_date=drill.drill_date,
            module="tatbikat",
            entity_type="drill_record",
            record_id=drill.id,
            responsible_role=drill.responsible or "İş Güvenliği Uzmanı / İşveren",
            today=today,
            completed=True,
            occurrence="completion",
        )
    latest_drill = max(completed_drills, key=lambda row: (row.drill_date, row.id), default=None)
    if latest_drill:
        renewal_date = add_years(latest_drill.drill_date, 1)
        covered = any(row.drill_date <= renewal_date for row in planned_drills)
        if not covered:
            _append(
                rows,
                company_id=cid,
                category="drill",
                source="Tatbikat Yenileme",
                title="Yıllık acil durum tatbikatı",
                due_date=renewal_date,
                module="tatbikat",
                entity_type="drill_record",
                record_id=latest_drill.id,
                responsible_role="İş Güvenliği Uzmanı / İşveren",
                today=today,
                occurrence="renewal",
            )

    for control in db.scalars(
        select(PeriodicControl).where(
            PeriodicControl.company_id == cid,
            PeriodicControl.is_active.is_(True),
        )
    ).all():
        if control.last_control_date:
            _append(
                rows,
                company_id=cid,
                category="periodic_control",
                source="Periyodik Kontrol",
                title=control.equipment_name,
                due_date=control.last_control_date,
                module="periyodik_kontrol",
                entity_type="periodic_control",
                record_id=control.id,
                responsible_role="İşveren / Kontrol sorumlusu",
                today=today,
                completed=True,
                occurrence="completion",
            )
        _append(
            rows,
            company_id=cid,
            category="periodic_control",
            source="Periyodik Kontrol Yenileme",
            title=control.equipment_name,
            due_date=control.next_due_date,
            module="periyodik_kontrol",
            entity_type="periodic_control",
            record_id=control.id,
            responsible_role="İşveren / Kontrol sorumlusu",
            today=today,
            occurrence="renewal",
        )

    for measurement in db.scalars(
        select(WorkplaceMeasurement).where(
            WorkplaceMeasurement.company_id == cid,
            WorkplaceMeasurement.is_active.is_(True),
        )
    ).all():
        title = (
            f"{measurement.measurement_type} — {measurement.location}"
            if measurement.location
            else measurement.measurement_type
        )
        _append(
            rows,
            company_id=cid,
            category="measurement",
            source="Ortam Ölçümü",
            title=title,
            due_date=measurement.measured_at,
            module="ortam_olcum",
            entity_type="workplace_measurement",
            record_id=measurement.id,
            responsible_role="İşveren / İş Güvenliği Uzmanı",
            today=today,
            completed=True,
            occurrence="completion",
        )
        _append(
            rows,
            company_id=cid,
            category="measurement",
            source="Ortam Ölçümü Yenileme",
            title=title,
            due_date=measurement.next_due_date,
            module="ortam_olcum",
            entity_type="workplace_measurement",
            record_id=measurement.id,
            responsible_role="İşveren / İş Güvenliği Uzmanı",
            today=today,
            occurrence="renewal",
        )

    for meeting in db.scalars(
        select(OhsCommitteeMeeting).where(
            OhsCommitteeMeeting.company_id == cid,
            OhsCommitteeMeeting.is_active.is_(True),
        )
    ).all():
        _append(
            rows,
            company_id=cid,
            category="committee",
            source="İSG Kurulu",
            title="Kurul toplantısı",
            due_date=meeting.meeting_date,
            module="isg_kurulu",
            entity_type="ohs_committee_meeting",
            record_id=meeting.id,
            responsible_role="İşveren / Kurul sekreteryası",
            today=today,
            completed=True,
            occurrence="completion",
        )
        _append(
            rows,
            company_id=cid,
            category="committee",
            source="İSG Kurulu",
            title="Sonraki kurul toplantısı",
            due_date=meeting.next_meeting_date,
            module="isg_kurulu",
            entity_type="ohs_committee_meeting",
            record_id=meeting.id,
            responsible_role="İşveren / Kurul sekreteryası",
            today=today,
            occurrence="next_meeting",
        )

    incidents = list(
        db.scalars(select(IncidentEvent).where(IncidentEvent.company_id == cid)).all()
    )
    incident_by_id = {int(row.id): row for row in incidents}
    for incident in incidents:
        if incident.sgk_reported:
            _append(
                rows,
                company_id=cid,
                branch_id=incident.branch_id,
                category="incident",
                source="İş Kazası Bildirimi",
                title=f"SGK bildirimi — {incident.form_no}",
                due_date=incident.sgk_report_date or incident.sgk_due_date,
                module="accident",
                entity_type="incident_event",
                record_id=incident.id,
                responsible_role="İşveren / İşveren vekili",
                today=today,
                completed=True,
                occurrence="completion",
            )
        elif incident.sgk_due_date:
            _append(
                rows,
                company_id=cid,
                branch_id=incident.branch_id,
                category="incident",
                source="İş Kazası Bildirimi",
                title=f"SGK bildirim süresi — {incident.form_no}",
                due_date=incident.sgk_due_date,
                module="accident",
                entity_type="incident_event",
                record_id=incident.id,
                responsible_role="İşveren / İşveren vekili",
                today=today,
            )
    for dof in db.scalars(
        select(IncidentDof).where(IncidentDof.incident_id.in_(list(incident_by_id) or [-1]))
    ).all():
        incident = incident_by_id.get(int(dof.incident_id))
        is_completed = incident_dof_completed(dof.status)
        _append(
            rows,
            company_id=cid,
            branch_id=getattr(incident, "branch_id", None),
            category="capa",
            source="DÖF",
            title=f"Olay DÖF ({dof.dof_no})",
            due_date=(dof.completion_date or dof.term_date) if is_completed else dof.term_date,
            module="capa",
            entity_type="incident_dof",
            record_id=dof.id,
            responsible_role=dof.responsible_person or "DÖF sorumlusu",
            today=today,
            completed=is_completed,
            occurrence="completion" if is_completed else "deadline",
            detail=dof.finding,
        )

    for document in db.scalars(
        select(DocumentRecord).where(
            DocumentRecord.company_id == cid,
            DocumentRecord.is_active.is_(True),
            DocumentRecord.valid_until.is_not(None),
        )
    ).all():
        safe_title = "Sağlık belgesi" if document.category == DocumentCategory.HEALTH else document.title
        _append(
            rows,
            company_id=cid,
            branch_id=document.branch_id,
            category="document",
            source="Doküman",
            title=safe_title,
            due_date=document.valid_until,
            module="documents",
            entity_type="document_record",
            record_id=document.id,
            responsible_role="Kayıt sorumlusu",
            today=today,
        )

    for plan in db.scalars(
        select(EmergencyPlan).where(
            EmergencyPlan.company_id == cid,
            EmergencyPlan.is_active.is_(True),
            EmergencyPlan.next_review_date.is_not(None),
        )
    ).all():
        _append(
            rows,
            company_id=cid,
            category="emergency_plan",
            source="Acil Durum Planı",
            title=plan.title,
            due_date=plan.next_review_date,
            module="acil_plan",
            entity_type="emergency_plan",
            record_id=plan.id,
            responsible_role="İş Güvenliği Uzmanı / İşveren",
            today=today,
            occurrence="review",
        )

    for plan_item in db.scalars(
        select(AnnualPlanItem).where(
            AnnualPlanItem.company_id == cid,
            AnnualPlanItem.deleted_at.is_(None),
            AnnualPlanItem.status != AnnualPlanStatus.CANCELLED,
            AnnualPlanItem.target_date.is_not(None),
        )
    ).all():
        is_completed = plan_item.status == AnnualPlanStatus.COMPLETED
        _append(
            rows,
            company_id=cid,
            category="annual_plan",
            source="Yıllık Plan",
            title=plan_item.activity,
            due_date=(plan_item.completion_date or plan_item.target_date) if is_completed else plan_item.target_date,
            module="annual_plans",
            entity_type="annual_plan_item",
            record_id=plan_item.id,
            responsible_role=plan_item.responsible_name or "Plan sorumlusu",
            today=today,
            completed=is_completed,
            occurrence="completion" if is_completed else "deadline",
            detail=plan_item.description,
        )

    # Health rows stay workplace-level aggregate-only.  Branching a one-person
    # group could make a medical due date identifiable in a small workplace.
    health_due_rows = db.execute(
        select(HealthRecord.next_examination_date, func.count(HealthRecord.id))
        .where(
            HealthRecord.company_id == cid,
            HealthRecord.deleted_at.is_(None),
            HealthRecord.next_examination_date.is_not(None),
        )
        .group_by(HealthRecord.next_examination_date)
    ).all()
    for due, total in health_due_rows:
        _append(
            rows,
            company_id=cid,
            category="health",
            source="Sağlık Gözetimi",
            title=f"{int(total)} çalışanın periyodik muayene tarihi",
            due_date=due,
            module="health",
            entity_type="health_examination_group",
            responsible_role="İşyeri Hekimi",
            today=today,
            detail="Kişisel sağlık ayrıntıları bu görünümde paylaşılmaz.",
        )

    for assignment in db.scalars(
        select(WorkplaceAssignment).where(
            WorkplaceAssignment.company_id == cid,
            WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
            WorkplaceAssignment.end_date.is_not(None),
        )
    ).all():
        _append(
            rows,
            company_id=cid,
            category="assignment",
            source="İSG Görevlendirmesi",
            title=f"{assignment.professional_type.value} görevlendirme bitişi",
            due_date=assignment.end_date,
            module="assignments",
            entity_type="workplace_assignment",
            record_id=assignment.id,
            responsible_role="OSGB Yöneticisi / İşveren",
            today=today,
        )

    branch_names = {
        int(branch.id): branch.name
        for branch in db.scalars(
            select(Branch).where(Branch.company_id == cid, Branch.is_active.is_(True))
        ).all()
    }
    for row in rows:
        row["branch_name"] = branch_names.get(row["branch_id"]) if row["branch_id"] else "İşyeri geneli"
    return rows


def build_workplace_obligations(
    db: Session,
    company,
    *,
    branch_id: int | None = None,
    category: str | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = 1,
    page_size: int = 25,
    today: date | None = None,
) -> dict:
    today = today or date.today()
    all_rows = collect_workplace_obligations(db, company, today=today)

    if branch_id is not None:
        all_rows = [row for row in all_rows if row["branch_id"] == branch_id]
    if date_from:
        all_rows = [row for row in all_rows if row["due_date"] >= date_from.isoformat()]
    if date_to:
        all_rows = [row for row in all_rows if row["due_date"] <= date_to.isoformat()]

    category_counts = {key: 0 for key in CATEGORY_LABELS}
    for row in all_rows:
        category_counts[row["category"]] += 1

    if category:
        all_rows = [row for row in all_rows if row["category"] == category]

    summary = {key: 0 for key in STATUS_LABELS}
    for row in all_rows:
        summary[row["status"]] += 1
    summary["total"] = len(all_rows)

    if status:
        all_rows = [row for row in all_rows if row["status"] == status]

    all_rows.sort(
        key=lambda row: (
            STATUS_ORDER[row["status"]],
            row["due_date"] if row["status"] != "completed" else "9999-12-31",
            row["source"],
            row["title"],
            row["key"],
        )
    )
    # Completed history is still deterministic, but newest completions are more
    # useful than oldest ones once their lower-priority group is reached.
    pending = [row for row in all_rows if row["status"] != "completed"]
    completed = sorted(
        (row for row in all_rows if row["status"] == "completed"),
        key=lambda row: (row["due_date"], row["key"]),
        reverse=True,
    )
    all_rows = pending + completed

    total = len(all_rows)
    total_pages = max(1, ceil(total / page_size))
    safe_page = min(page, total_pages)
    start = (safe_page - 1) * page_size
    page_rows = all_rows[start : start + page_size]

    branches = list(
        db.scalars(
            select(Branch)
            .where(Branch.company_id == int(company.id), Branch.is_active.is_(True))
            .order_by(Branch.name, Branch.id)
        ).all()
    )
    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "company": {"id": int(company.id), "name": company.name},
        "thresholds": {"very_soon_days": 7, "approaching_days": 30},
        "privacy": {
            "medical_data_mode": "aggregate_only",
            "sensitive_fields_exposed": False,
        },
        "filters": {
            "branch_id": branch_id,
            "category": category,
            "status": status,
            "date_from": date_from.isoformat() if date_from else None,
            "date_to": date_to.isoformat() if date_to else None,
        },
        "statuses": [
            {"code": key, "label": label, "count": summary[key]}
            for key, label in STATUS_LABELS.items()
        ],
        "categories": [
            {"code": key, "label": label, "count": category_counts[key]}
            for key, label in CATEGORY_LABELS.items()
            if category_counts[key]
        ],
        "branches": [
            {"id": int(branch.id), "name": branch.name}
            for branch in branches
        ],
        "summary": summary,
        "pagination": {
            "page": safe_page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
            "has_previous": safe_page > 1,
            "has_next": safe_page < total_pages,
        },
        "items": page_rows,
    }
