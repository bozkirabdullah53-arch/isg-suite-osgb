"""İSG süre / termin bildirimleri.

Firma: geciken İSG kaydı, doküman geçerliliği, sağlık muayenesi, yıllık plan.
OSGB: biten/yaklaşan görevlendirme, sözleşme, atanmamış profesyonel, KATİP eksik.
"""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.models.entities import (
    AnnualPlanEvalEvidence,
    AnnualPlanEvaluation,
    AnnualPlanEvaluationItem,
    AnnualPlanItem,
    AnnualPlanStatus,
    AssignmentStatus,
    ChemicalProduct,
    Company,
    DocumentRecord,
    Employee,
    HealthRecord,
    IsgProfessional,
    IsgRecord,
    Notification,
    NotificationType,
    OsgbOrganization,
    RecordStatus,
    ServiceContract,
    WorkplaceAssignment,
)


def rebuild_company_notifications(db: Session, company_id: int) -> int:
    db.execute(
        delete(Notification).where(
            Notification.company_id == company_id,
            Notification.user_id.is_(None),
            or_(
                Notification.entity_type.is_(None),
                Notification.entity_type.in_(
                    (
                        "isg_record",
                        "document",
                        "health_record",
                        "annual_plan",
                        "annual_eval",
                        "chemical_product",
                    )
                ),
            ),
        )
    )
    today = date.today()
    warning_date = today + timedelta(days=30)
    notifications: list[Notification] = []

    overdue_isg = db.scalars(
        select(IsgRecord).where(
            IsgRecord.company_id == company_id,
            IsgRecord.due_date.is_not(None),
            IsgRecord.due_date < today,
            IsgRecord.status != RecordStatus.COMPLETED,
        )
    ).all()
    for item in overdue_isg:
        notifications.append(
            Notification(
                company_id=company_id,
                type=NotificationType.CRITICAL,
                title="Termin tarihi geçen İSG kaydı",
                message=f"{item.title} kaydının termin tarihi {item.due_date} tarihinde doldu.",
                entity_type="isg_record",
                entity_id=str(item.id),
            )
        )

    expiring_docs = db.scalars(
        select(DocumentRecord).where(
            DocumentRecord.company_id == company_id,
            DocumentRecord.valid_until.is_not(None),
            DocumentRecord.valid_until <= warning_date,
            DocumentRecord.is_active.is_(True),
        )
    ).all()
    for item in expiring_docs:
        notifications.append(
            Notification(
                company_id=company_id,
                type=NotificationType.WARNING if item.valid_until >= today else NotificationType.CRITICAL,
                title="Doküman geçerlilik uyarısı",
                message=f"{item.title} dokümanının geçerlilik tarihi {item.valid_until}.",
                entity_type="document",
                entity_id=str(item.id),
            )
        )

    exams = db.scalars(
        select(HealthRecord).where(
            HealthRecord.company_id == company_id,
            HealthRecord.deleted_at.is_(None),
            HealthRecord.next_examination_date.is_not(None),
            HealthRecord.next_examination_date <= warning_date,
        )
    ).all()
    emp_ids = {item.employee_id for item in exams}
    emp_names: dict[int, str] = {}
    if emp_ids:
        emp_names = {
            e.id: e.full_name
            for e in db.scalars(select(Employee).where(Employee.id.in_(emp_ids))).all()
        }
    for item in exams:
        who = emp_names.get(item.employee_id) or f"Personel #{item.employee_id}"
        notifications.append(
            Notification(
                company_id=company_id,
                type=NotificationType.WARNING,
                title="Yaklaşan sağlık muayenesi",
                message=f"{who} için muayene tarihi {item.next_examination_date}.",
                entity_type="health_record",
                entity_id=str(item.id),
            )
        )

    delayed = db.scalars(
        select(AnnualPlanItem).where(
            AnnualPlanItem.company_id == company_id,
            AnnualPlanItem.deleted_at.is_(None),
            AnnualPlanItem.status == AnnualPlanStatus.DELAYED,
        )
    ).all()
    for item in delayed:
        notifications.append(
            Notification(
                company_id=company_id,
                type=NotificationType.WARNING,
                title="Geciken yıllık plan faaliyeti",
                message=f"{item.year}/{item.month}: {item.activity}",
                entity_type="annual_plan",
                entity_id=str(item.id),
            )
        )

    # 0.9.137 — Yıllık plan değerlendirme uyarıları
    year = today.year
    plan_count = db.scalar(
        select(AnnualPlanItem.id).where(
            AnnualPlanItem.company_id == company_id,
            AnnualPlanItem.year == year,
            AnnualPlanItem.deleted_at.is_(None),
        ).limit(1)
    )
    ev = db.scalar(
        select(AnnualPlanEvaluation).where(
            AnnualPlanEvaluation.company_id == company_id,
            AnnualPlanEvaluation.year == year,
            AnnualPlanEvaluation.is_active.is_(True),
        )
    )
    if plan_count and not ev:
        notifications.append(
            Notification(
                company_id=company_id,
                type=NotificationType.WARNING,
                title="Yıllık değerlendirme henüz başlatılmadı",
                message=f"{year} yılı için plan kalemleri var; değerlendirme başlatılmamış.",
                entity_type="annual_eval",
                entity_id=str(year),
            )
        )
    elif ev:
        if ev.report_status in ("hazirlaniyor", "hazirlanmadi", "revizyon"):
            open_items = list(
                db.scalars(
                    select(AnnualPlanEvaluationItem).where(
                        AnnualPlanEvaluationItem.evaluation_id == ev.id,
                        AnnualPlanEvaluationItem.is_active.is_(True),
                        AnnualPlanEvaluationItem.outcome_status.in_(
                            ("planlandi", "devam", "ertelendi", "kismi")
                        ),
                    ).limit(40)
                ).all()
            )
            overdue_n = 0
            for row in open_items:
                plan = db.get(AnnualPlanItem, row.plan_item_id)
                if plan and plan.target_date and plan.target_date < today and row.outcome_status in ("planlandi", "devam"):
                    overdue_n += 1
            if overdue_n:
                notifications.append(
                    Notification(
                        company_id=company_id,
                        type=NotificationType.CRITICAL,
                        title="Değerlendirme geciken faaliyetler",
                        message=f"{year}: planlanan tarihi geçen {overdue_n} faaliyet henüz tamamlanmadı.",
                        entity_type="annual_eval",
                        entity_id=str(ev.id),
                    )
                )
            with_ev = set(
                db.scalars(
                    select(AnnualPlanEvalEvidence.evaluation_item_id).where(
                        AnnualPlanEvalEvidence.is_active.is_(True),
                        AnnualPlanEvalEvidence.evaluation_item_id.in_(
                            select(AnnualPlanEvaluationItem.id).where(
                                AnnualPlanEvaluationItem.evaluation_id == ev.id,
                                AnnualPlanEvaluationItem.is_active.is_(True),
                            )
                        ),
                    )
                ).all()
            )
            need_ev = list(
                db.scalars(
                    select(AnnualPlanEvaluationItem.id).where(
                        AnnualPlanEvaluationItem.evaluation_id == ev.id,
                        AnnualPlanEvaluationItem.is_active.is_(True),
                        AnnualPlanEvaluationItem.outcome_status.in_(
                            ("tamam", "gecikmeli_tamam", "kismi", "devam")
                        ),
                    )
                ).all()
            )
            missing_ev_n = sum(1 for i in need_ev if i not in with_ev)
            if missing_ev_n:
                notifications.append(
                    Notification(
                        company_id=company_id,
                        type=NotificationType.WARNING,
                        title="Kanıt belgesi eksik faaliyetler",
                        message=f"{year}: {missing_ev_n} değerlendirilmiş faaliyette kanıt yok.",
                        entity_type="annual_eval",
                        entity_id=str(ev.id),
                    )
                )
        if ev.report_status == "hekim_bekliyor":
            notifications.append(
                Notification(
                    company_id=company_id,
                    type=NotificationType.INFO,
                    title="Hekim değerlendirmesi bekleniyor",
                    message=f"{year} yıllık değerlendirme hekim onayında.",
                    entity_type="annual_eval",
                    entity_id=str(ev.id),
                )
            )
        if ev.report_status == "isveren_bekliyor":
            notifications.append(
                Notification(
                    company_id=company_id,
                    type=NotificationType.INFO,
                    title="İşveren onayı bekleniyor",
                    message=f"{year} yıllık değerlendirme işveren onayında.",
                    entity_type="annual_eval",
                    entity_id=str(ev.id),
                )
            )

    # 0.9.122 — SDS / PKD gözden geçirme
    chemicals = db.scalars(
        select(ChemicalProduct).where(
            ChemicalProduct.company_id == company_id,
            ChemicalProduct.is_active.is_(True),
            ChemicalProduct.next_review_date.is_not(None),
            ChemicalProduct.next_review_date <= warning_date,
        )
    ).all()
    for item in chemicals:
        overdue = bool(item.next_review_date and item.next_review_date < today)
        notifications.append(
            Notification(
                company_id=company_id,
                type=NotificationType.CRITICAL if overdue else NotificationType.WARNING,
                title="SDS gözden geçirme" + (" gecikmiş" if overdue else " yaklaşıyor"),
                message=(
                    f"{item.product_name} için SDS gözden geçirme tarihi "
                    f"{item.next_review_date}."
                    + ("" if item.has_sds_file else " SDS dosyası henüz işaretlenmemiş.")
                ),
                entity_type="chemical_product",
                entity_id=str(item.id),
            )
        )

    db.add_all(notifications)
    db.commit()
    return len(notifications)


def rebuild_osgb_notifications(db: Session, osgb_id: int) -> int:
    """OSGB operasyon uyarıları (görevlendirme / sözleşme / kadro)."""
    company_ids = list(
        db.scalars(select(Company.id).where(Company.osgb_id == osgb_id)).all()
    )
    # Önceki OSGB seviye bildirimlerini temizle
    osgb_types = (
        "osgb_assignment",
        "osgb_contract",
        "osgb_professional",
        "osgb_katip",
        "osgb_summary",
    )
    if company_ids:
        db.execute(
            delete(Notification).where(
                Notification.user_id.is_(None),
                Notification.entity_type.in_(osgb_types),
                or_(Notification.company_id.is_(None), Notification.company_id.in_(company_ids)),
            )
        )
    else:
        db.execute(
            delete(Notification).where(
                Notification.user_id.is_(None),
                Notification.entity_type.in_(osgb_types),
                Notification.company_id.is_(None),
            )
        )

    today = date.today()
    warn = today + timedelta(days=30)
    company_names = {
        c.id: c.name
        for c in db.scalars(select(Company).where(Company.osgb_id == osgb_id)).all()
    }
    pro_names = {
        p.id: p.full_name
        for p in db.scalars(select(IsgProfessional).where(IsgProfessional.osgb_id == osgb_id)).all()
    }
    notifications: list[Notification] = []

    assignments = list(
        db.scalars(
            select(WorkplaceAssignment).where(WorkplaceAssignment.osgb_id == osgb_id)
        ).all()
    )
    active = [
        a
        for a in assignments
        if a.status == AssignmentStatus.ACTIVE
        or (isinstance(a.status, str) and str(a.status).lower() == "active")
    ]

    for a in active:
        firm = company_names.get(a.company_id, f"İşyeri #{a.company_id}")
        who = pro_names.get(a.professional_id, f"Profesyonel #{a.professional_id}")
        if a.end_date and a.end_date < today:
            notifications.append(
                Notification(
                    company_id=a.company_id,
                    type=NotificationType.CRITICAL,
                    title="Görevlendirme süresi dolmuş",
                    message=f"{who} → {firm}: bitiş {a.end_date}. Durum hâlâ aktif.",
                    entity_type="osgb_assignment",
                    entity_id=str(a.id),
                )
            )
        elif a.end_date and a.end_date <= warn:
            notifications.append(
                Notification(
                    company_id=a.company_id,
                    type=NotificationType.WARNING,
                    title="Görevlendirme süresi yaklaşıyor",
                    message=f"{who} → {firm}: bitiş {a.end_date}.",
                    entity_type="osgb_assignment",
                    entity_id=str(a.id),
                )
            )
        if not (a.isg_katip_contract_number or "").strip():
            notifications.append(
                Notification(
                    company_id=a.company_id,
                    type=NotificationType.WARNING,
                    title="İSG-KATİP bildirim no eksik",
                    message=f"{who} → {firm} görevlendirmesinde KATİP no yok.",
                    entity_type="osgb_katip",
                    entity_id=str(a.id),
                )
            )

    assigned_pro_ids = {a.professional_id for a in active}
    for p in db.scalars(
        select(IsgProfessional).where(
            IsgProfessional.osgb_id == osgb_id,
            IsgProfessional.is_active.is_(True),
        )
    ).all():
        if p.id not in assigned_pro_ids:
            notifications.append(
                Notification(
                    company_id=None,
                    type=NotificationType.WARNING,
                    title="Atanmamış İSG profesyoneli",
                    message=f"{p.full_name} aktif ama hiçbir işyerine görevlendirilmemiş.",
                    entity_type="osgb_professional",
                    entity_id=str(p.id),
                )
            )
        if not (p.certificate_number or "").strip():
            notifications.append(
                Notification(
                    company_id=None,
                    type=NotificationType.WARNING,
                    title="Profesyonel belge no eksik",
                    message=f"{p.full_name}: sertifika / belge numarası kayıtlı değil.",
                    entity_type="osgb_professional",
                    entity_id=str(p.id),
                )
            )

    contracts = db.scalars(
        select(ServiceContract).where(ServiceContract.osgb_id == osgb_id)
    ).all()
    for c in contracts:
        st = (c.status or "").lower()
        if st not in ("active", "aktif", ""):
            continue
        firm = company_names.get(c.company_id, f"İşyeri #{c.company_id}")
        if c.end_date and c.end_date < today:
            notifications.append(
                Notification(
                    company_id=c.company_id,
                    type=NotificationType.CRITICAL,
                    title="Hizmet sözleşmesi süresi dolmuş",
                    message=f"{firm} — sözleşme {c.contract_number}, bitiş {c.end_date}.",
                    entity_type="osgb_contract",
                    entity_id=str(c.id),
                )
            )
        elif c.end_date and c.end_date <= warn:
            notifications.append(
                Notification(
                    company_id=c.company_id,
                    type=NotificationType.WARNING,
                    title="Hizmet sözleşmesi süresi yaklaşıyor",
                    message=f"{firm} — sözleşme {c.contract_number}, bitiş {c.end_date}.",
                    entity_type="osgb_contract",
                    entity_id=str(c.id),
                )
            )

    if not company_names and not pro_names and not assignments:
        notifications.append(
            Notification(
                company_id=None,
                type=NotificationType.INFO,
                title="OSGB operasyon kaydı yok",
                message=(
                    "Bu OSGB’ye bağlı işyeri, profesyonel veya görevlendirme bulunamadı. "
                    "İşyerleri ve İSG Profesyonelleri menülerinden kayıt ekleyin."
                ),
                entity_type="osgb_summary",
                entity_id=str(osgb_id),
            )
        )

    db.add_all(notifications)
    db.commit()
    return len(notifications)


def rebuild_all_notifications(db: Session, *, osgb_id: int | None = None, company_id: int | None = None) -> int:
    total = 0
    if company_id:
        total += rebuild_company_notifications(db, company_id)
    if osgb_id:
        total += rebuild_osgb_notifications(db, osgb_id)
        # OSGB’ye bağlı her aktif işyerinin firma bildirimlerini de üret
        for cid in db.scalars(
            select(Company.id).where(Company.osgb_id == osgb_id, Company.is_active.is_(True))
        ).all():
            if company_id and cid == company_id:
                continue
            total += rebuild_company_notifications(db, cid)
    elif not company_id:
        # Tüm OSGB’ler (global admin)
        for oid in db.scalars(select(OsgbOrganization.id)).all():
            total += rebuild_osgb_notifications(db, oid)
            for cid in db.scalars(
                select(Company.id).where(Company.osgb_id == oid, Company.is_active.is_(True))
            ).all():
                total += rebuild_company_notifications(db, cid)
    return total
