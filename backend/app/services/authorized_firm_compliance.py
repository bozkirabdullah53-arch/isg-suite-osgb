"""Yetkili firma uygunluk, uyarı, skor ve tenant güvenliği hesapları."""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.authorized_firm import (
    AuthorizedFirmDocument,
    AuthorizedFirmProfile,
    ComplianceScoreSnapshot,
    ProfessionalComplianceProfile,
)
from app.models.entities import (
    AssignmentStatus,
    AuditLog,
    Company,
    DocumentRecord,
    Employee,
    IsgProfessional,
    Notification,
    NotificationType,
    OsgbOrganization,
    ServiceContract,
    ServiceVisit,
    VisitStatus,
    WorkplaceAssignment,
)
from app.services.workplace_status import build_workplace_status


STATUS_LABELS = {
    "ready": "Hazır",
    "attention": "Dikkat gerekli",
    "significant": "Önemli eksikler",
    "critical": "Kritik eksikler",
}

PROFESSIONAL_STATUS_LABELS = {
    "compliant": "Uygun",
    "partially_compliant": "Kısmen uygun",
    "missing_documents": "Belge eksik",
    "expired_documents": "Belge süresi dolmuş",
    "assignment_problem": "Görevlendirme sorunu",
    "review_required": "İnceleme gerekli",
}


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value) or "")


def _date_value(value: date | None) -> str | None:
    return value.isoformat() if value else None


def _datetime_value(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _json_list(raw: str | None) -> list:
    try:
        value = json.loads(raw or "[]")
    except (TypeError, ValueError):
        return []
    return value if isinstance(value, list) else []


def expiry_state(value: date | None, *, today: date | None = None) -> dict[str, Any]:
    current = today or date.today()
    if value is None:
        return {"code": "missing", "label": "Tarih eksik", "days_left": None, "severity": "warning"}
    days_left = (value - current).days
    if days_left < 0:
        return {"code": "expired", "label": "Süresi dolmuş", "days_left": days_left, "severity": "critical"}
    if days_left <= 30:
        return {"code": "due_30", "label": "30 gün içinde dolacak", "days_left": days_left, "severity": "warning"}
    if days_left <= 60:
        return {"code": "due_60", "label": "60 gün içinde dolacak", "days_left": days_left, "severity": "warning"}
    if days_left <= 90:
        return {"code": "due_90", "label": "90 gün içinde dolacak", "days_left": days_left, "severity": "info"}
    return {"code": "valid", "label": "Geçerli", "days_left": days_left, "severity": "ok"}


def validate_profile_dates(values: dict[str, Any]) -> None:
    start = values.get("authorization_start_date")
    issue = values.get("authorization_issue_date")
    end = values.get("authorization_expiry_date")
    if start and end and end < start:
        raise ValueError("Yetki bitiş tarihi başlangıç tarihinden önce olamaz.")
    if issue and end and end < issue:
        raise ValueError("Yetki bitiş tarihi düzenlenme tarihinden önce olamaz.")


def validate_document_dates(values: dict[str, Any]) -> None:
    start = values.get("start_date")
    end = values.get("expiry_date")
    review = values.get("review_date")
    renewal = values.get("renewal_date")
    if start and end and end < start:
        raise ValueError("Belge bitiş tarihi başlangıç tarihinden önce olamaz.")
    if review and renewal and renewal < review:
        raise ValueError("Belge yenileme tarihi gözden geçirme tarihinden önce olamaz.")


def validate_professional_dates(values: dict[str, Any]) -> None:
    issue = values.get("certificate_issue_date")
    expiry = values.get("certificate_expiry_date")
    review = values.get("document_review_date")
    renewal = values.get("document_renewal_date")
    if issue and expiry and expiry < issue:
        raise ValueError("Profesyonel belge bitiş tarihi düzenlenme tarihinden önce olamaz.")
    if review and renewal and renewal < review:
        raise ValueError("Profesyonel belge yenileme tarihi gözden geçirme tarihinden önce olamaz.")


def assignment_contract_coverage(
    db: Session,
    *,
    osgb_id: int,
    company_id: int,
    start_date: date,
    end_date: date | None,
) -> ServiceContract | None:
    period_condition = (
        ServiceContract.end_date.is_(None)
        if end_date is None
        else or_(ServiceContract.end_date.is_(None), ServiceContract.end_date >= end_date)
    )
    return db.scalar(
        select(ServiceContract)
        .where(
            ServiceContract.osgb_id == osgb_id,
            ServiceContract.company_id == company_id,
            func.lower(ServiceContract.status).in_(("active", "aktif", "")),
            ServiceContract.start_date <= start_date,
            period_condition,
        )
        .order_by(ServiceContract.start_date.desc(), ServiceContract.id.desc())
        .limit(1)
    )


def validate_authorized_assignment_period(
    db: Session,
    *,
    osgb_id: int,
    company_id: int,
    start_date: date,
    end_date: date | None,
) -> None:
    profile = db.scalar(
        select(AuthorizedFirmProfile.id).where(
            AuthorizedFirmProfile.osgb_id == osgb_id,
            AuthorizedFirmProfile.company_id == company_id,
            AuthorizedFirmProfile.is_active.is_(True),
        )
    )
    if profile is None:
        return
    if assignment_contract_coverage(
        db,
        osgb_id=osgb_id,
        company_id=company_id,
        start_date=start_date,
        end_date=end_date,
    ) is None:
        raise ValueError(
            "Yetkili firma görevlendirmesi, geçerli hizmet sözleşmesinin tarih aralığı içinde olmalıdır."
        )


def _document_payload(item: AuthorizedFirmDocument, *, today: date) -> dict[str, Any]:
    state = expiry_state(item.expiry_date, today=today)
    return {
        "id": item.id,
        "document_record_id": item.document_record_id,
        "document_type": item.document_type,
        "title": item.title,
        "mandatory": bool(item.mandatory),
        "start_date": _date_value(item.start_date),
        "expiry_date": _date_value(item.expiry_date),
        "review_date": _date_value(item.review_date),
        "renewal_date": _date_value(item.renewal_date),
        "notes": item.notes,
        "is_active": bool(item.is_active),
        "validity": state,
    }


def _contract_covers_assignment(db: Session, assignment: WorkplaceAssignment) -> bool:
    return assignment_contract_coverage(
        db,
        osgb_id=assignment.osgb_id,
        company_id=assignment.company_id,
        start_date=assignment.start_date,
        end_date=assignment.end_date,
    ) is not None


def evaluate_professional_compliance(
    db: Session,
    professional: IsgProfessional,
    *,
    company_id: int | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    current = today or date.today()
    meta = db.scalar(
        select(ProfessionalComplianceProfile).where(
            ProfessionalComplianceProfile.professional_id == professional.id,
            ProfessionalComplianceProfile.osgb_id == professional.osgb_id,
        )
    )
    issue_date = meta.certificate_issue_date if meta else professional.certificate_date
    expiry_date = meta.certificate_expiry_date if meta else None
    validity = expiry_state(expiry_date, today=current)
    assignment_stmt = select(WorkplaceAssignment).where(
        WorkplaceAssignment.professional_id == professional.id,
        WorkplaceAssignment.osgb_id == professional.osgb_id,
    )
    if company_id is not None:
        assignment_stmt = assignment_stmt.where(WorkplaceAssignment.company_id == company_id)
    assignments = list(db.scalars(assignment_stmt.order_by(WorkplaceAssignment.start_date.desc())).all())
    active_assignments = [
        item
        for item in assignments
        if _enum_value(item.status).lower() == "active"
    ]

    checks: list[dict[str, Any]] = []

    def add(code: str, label: str, passed: bool, detail: str, severity: str = "warning") -> None:
        checks.append(
            {"code": code, "label": label, "passed": bool(passed), "detail": detail, "severity": severity}
        )

    role = _enum_value(professional.professional_type)
    add("role", "Profesyonel rolü", bool(role), role or "Rol kaydı eksik.", "critical")
    class_required = role == "safety_specialist"
    add(
        "certificate_class",
        "Belge sınıfı",
        bool(professional.certificate_class) or not class_required,
        professional.certificate_class or ("Bu rol için sınıf zorunlu değil." if not class_required else "Belge sınıfı eksik."),
    )
    add(
        "certificate_number",
        "Belge numarası",
        bool((professional.certificate_number or "").strip()),
        professional.certificate_number or "Belge numarası eksik.",
        "critical",
    )
    add(
        "certificate_issue_date",
        "Belge düzenlenme tarihi",
        issue_date is not None,
        _date_value(issue_date) or "Düzenlenme tarihi eksik.",
    )
    add(
        "certificate_validity",
        "Belge geçerliliği",
        validity["code"] == "valid",
        f"{validity['label']}" + (f" ({validity['days_left']} gün)" if validity["days_left"] is not None else ""),
        "critical" if validity["code"] == "expired" else "warning",
    )
    document_state = meta.required_documents_status if meta else "review_required"
    add(
        "required_documents",
        "Zorunlu belgeler",
        document_state == "complete",
        {
            "complete": "Zorunlu belge listesi tamamlandı.",
            "incomplete": "Zorunlu belgeler eksik.",
            "review_required": "Zorunlu belgeler yönetici incelemesi bekliyor.",
        }.get(document_state, "Belge durumu belirsiz."),
        "critical" if document_state == "incomplete" else "warning",
    )
    add(
        "assignments",
        "Aktif görevlendirme",
        bool(active_assignments),
        f"{len(active_assignments)} aktif görevlendirme." if active_assignments else "Aktif görevlendirme yok.",
        "critical",
    )

    period_problem = False
    contract_problem = False
    required_total = planned_total = actual_total = 0
    for assignment in active_assignments:
        required_total += int(assignment.required_minutes_monthly or 0)
        planned_total += int(assignment.planned_minutes_monthly or 0)
        actual_total += int(assignment.actual_minutes_monthly or 0)
        if assignment.end_date and assignment.end_date < current:
            period_problem = True
        if assignment.end_date and assignment.end_date < assignment.start_date:
            period_problem = True
        if not _contract_covers_assignment(db, assignment):
            contract_problem = True
    add(
        "assignment_period",
        "Görevlendirme tarihleri",
        bool(active_assignments) and not period_problem,
        "Aktif tarih aralıkları geçerli." if active_assignments and not period_problem else "Süresi geçmiş veya tutarsız görevlendirme var.",
        "critical",
    )
    add(
        "contract_coverage",
        "Sözleşme kapsamı",
        bool(active_assignments) and not contract_problem,
        "Görevlendirmeler geçerli sözleşme aralığında." if active_assignments and not contract_problem else "Sözleşme dışı veya sözleşmesiz görevlendirme var.",
        "critical",
    )
    minutes_ok = bool(active_assignments) and planned_total >= required_total and actual_total >= min(planned_total, required_total)
    add(
        "service_minutes",
        "Aylık hizmet süresi",
        minutes_ok,
        f"Zorunlu {required_total} dk · planlanan {planned_total} dk · gerçekleşen {actual_total} dk.",
    )

    failed = [item for item in checks if not item["passed"]]
    failed_codes = {item["code"] for item in failed}
    if validity["code"] == "expired":
        status = "expired_documents"
    elif "certificate_number" in failed_codes or document_state == "incomplete":
        status = "missing_documents"
    elif failed_codes & {"assignments", "assignment_period", "contract_coverage"}:
        status = "assignment_problem"
    elif not failed:
        status = "compliant"
    elif validity["code"] in {"missing", "due_30", "due_60", "due_90"} or document_state == "review_required":
        status = "review_required"
    else:
        status = "partially_compliant"

    score = round(100 * sum(1 for item in checks if item["passed"]) / len(checks)) if checks else 0
    return {
        "professional_id": professional.id,
        "osgb_id": professional.osgb_id,
        "full_name": professional.full_name,
        "professional_type": role,
        "certificate_class": professional.certificate_class,
        "certificate_number": professional.certificate_number,
        "certificate_issue_date": _date_value(issue_date),
        "certificate_expiry_date": _date_value(expiry_date),
        "document_review_date": _date_value(meta.document_review_date if meta else None),
        "document_renewal_date": _date_value(meta.document_renewal_date if meta else None),
        "required_documents_status": document_state,
        "required_documents_note": meta.required_documents_note if meta else None,
        "status": status,
        "status_label": PROFESSIONAL_STATUS_LABELS[status],
        "score": score,
        "validity": validity,
        "checks": checks,
        "assignment_count": len(active_assignments),
        "required_minutes_monthly": required_total,
        "planned_minutes_monthly": planned_total,
        "actual_minutes_monthly": actual_total,
    }


def _category(
    code: str,
    label: str,
    score: int,
    detail: str,
    action: str,
    *,
    weight: int = 10,
    critical: bool = False,
) -> dict[str, Any]:
    return {
        "code": code,
        "label": label,
        "score": max(0, min(100, int(score))),
        "weight": weight,
        "detail": detail,
        "recommended_action": action,
        "passed": score >= 80,
        "critical": bool(critical),
    }


def _status_item(center: dict[str, Any], code: str) -> dict[str, Any]:
    for item in center.get("items") or []:
        if item.get("code") == code:
            return item
    return {}


def _item_score(item: dict[str, Any]) -> int:
    return {
        "completed": 100,
        "due_soon": 80,
        "attention": 60,
        "informational": 100,
        "missing": 0,
        "overdue": 0,
    }.get(item.get("status"), 0)


def _build_scores(
    profile: AuthorizedFirmProfile,
    documents: list[dict[str, Any]],
    professionals: list[dict[str, Any]],
    workplace: dict[str, Any],
    visits: list[ServiceVisit],
) -> dict[str, Any]:
    center = workplace.get("status_center") or {}
    required_profile_fields = (
        profile.firm_name,
        profile.firm_type,
        profile.province,
        profile.district,
        profile.address,
        profile.authorized_representative,
        profile.contact_email or profile.contact_phone,
        profile.hazard_class,
        profile.authorization_scope,
        profile.authorization_number,
        profile.authorization_start_date,
        profile.authorization_expiry_date,
    )
    profile_complete = sum(1 for value in required_profile_fields if value not in (None, ""))
    authorization_score = round(100 * profile_complete / len(required_profile_fields))
    auth_validity = expiry_state(profile.authorization_expiry_date)
    if auth_validity["code"] == "expired":
        authorization_score = min(authorization_score, 20)

    mandatory_docs = [item for item in documents if item["mandatory"] and item["is_active"]]
    valid_docs = [item for item in mandatory_docs if item["validity"]["code"] in {"valid", "due_90", "due_60", "due_30"}]
    document_score = round(100 * len(valid_docs) / len(mandatory_docs)) if mandatory_docs else 0
    professional_score = round(sum(item["score"] for item in professionals) / len(professionals)) if professionals else 0
    assignment_item = _status_item(center, "assignments")
    assignment_score = _item_score(assignment_item)
    if any(item["status"] == "assignment_problem" for item in professionals):
        assignment_score = min(assignment_score, 30)

    past_visits = [visit for visit in visits if visit.visit_date <= date.today()]
    completed_visits = [visit for visit in past_visits if _enum_value(visit.status).lower() == "completed"]
    visit_score = round(100 * len(completed_visits) / len(past_visits)) if past_visits else 0
    risk_score = _item_score(_status_item(center, "risk_assessment"))
    corrective_score = _item_score(_status_item(center, "capa"))
    training_score = _item_score(_status_item(center, "training"))
    health_score = _item_score(_status_item(center, "health_examinations"))
    inspection_score = int(center.get("completion_pct") or 0)

    categories = [
        _category("authorization", "Yetki kaydı tamlığı", authorization_score, f"{profile_complete}/{len(required_profile_fields)} alan tamamlandı; {auth_validity['label']}.", "Eksik yetki ve iletişim alanlarını tamamlayın.", critical=auth_validity["code"] == "expired"),
        _category("document_validity", "Belge geçerliliği", document_score, f"{len(valid_docs)}/{len(mandatory_docs)} zorunlu belge geçerli.", "Eksik veya süresi dolan belgeleri yenileyin.", critical=any(item["validity"]["code"] == "expired" for item in mandatory_docs)),
        _category("professional_availability", "Profesyonel uygunluğu", professional_score, f"{len(professionals)} sorumlu profesyonel değerlendirildi.", "Eksik belge ve profesyonel uygunluk kontrollerini tamamlayın.", critical=not professionals or any(item["status"] == "expired_documents" for item in professionals)),
        _category("assignments", "Görevlendirme tamlığı", assignment_score, assignment_item.get("detail") or "Görevlendirme verisi yok.", "Görevlendirme tarihlerini ve sözleşme kapsamını düzeltin.", critical=assignment_score < 50),
        _category("visits", "Ziyaret tamamlama", visit_score, f"{len(completed_visits)}/{len(past_visits)} geçmiş ziyaret tamamlandı.", "Gecikmiş ziyaretleri planlayın ve tamamlayın."),
        _category("risks", "Açık riskler", risk_score, _status_item(center, "risk_assessment").get("detail") or "Risk verisi yok.", "Risk değerlendirmesini tamamlayın ve kritik riskleri kapatın.", critical=risk_score == 0),
        _category("corrective_actions", "Düzeltici faaliyetler", corrective_score, _status_item(center, "capa").get("detail") or "DÖF verisi yok.", "Geciken düzeltici faaliyetleri sonuçlandırın.", critical=corrective_score == 0 and bool(_status_item(center, "capa").get("critical"))),
        _category("training", "Eğitim tamamlama", training_score, _status_item(center, "training").get("detail") or "Eğitim verisi yok.", "Eksik eğitimleri planlayın ve katılım kayıtlarını tamamlayın."),
        _category("health", "Sağlık gözetimi", health_score, _status_item(center, "health_examinations").get("detail") or "Sağlık özeti yok.", "Gecikmiş muayeneleri tamamlayın; klinik ayrıntıları yetkili rolde tutun.", critical=health_score == 0),
        _category("inspection", "Denetim hazırlığı", inspection_score, center.get("overall_label") or "Hazırlık verisi yok.", "Kritik eksik listesini kapatıp hazırlık paketini yeniden üretin.", critical=int((center.get("summary") or {}).get("critical") or 0) > 0),
    ]
    total_weight = sum(item["weight"] for item in categories)
    overall = round(sum(item["score"] * item["weight"] for item in categories) / total_weight) if total_weight else 0
    blockers = [
        {
            "code": item["code"],
            "title": item["label"],
            "detail": item["detail"],
            "recommended_action": item["recommended_action"],
        }
        for item in categories
        if item["critical"] and item["score"] < 80
    ]
    if blockers or overall < 50:
        status = "critical"
    elif overall < 70:
        status = "significant"
    elif overall < 85:
        status = "attention"
    else:
        status = "ready"

    workload_scores = []
    for item in professionals:
        required = int(item.get("required_minutes_monthly") or 0)
        planned = int(item.get("planned_minutes_monthly") or 0)
        actual = int(item.get("actual_minutes_monthly") or 0)
        if required:
            workload_scores.append(min(100, round(100 * min(planned, actual) / required)))
    workload_score = round(sum(workload_scores) / len(workload_scores)) if workload_scores else 0
    quality_categories = [
        _category("document_completeness", "Belge tamlığı", round((authorization_score + document_score) / 2), "Yetki ve zorunlu belge tamlığı.", "Eksik belge alanlarını tamamlayın."),
        _category("timely_visits", "Zamanında ziyaret", visit_score, "Tamamlanan geçmiş ziyaret oranı.", "Ziyaret planını dengeleyin."),
        _category("risk_closure", "Risk kapatma", risk_score, "Açık ve gecikmiş risk durumu.", "Öncelikli riskleri kapatın."),
        _category("training_completion", "Eğitim tamamlama", training_score, "Eğitim kayıt durumu.", "Eğitim eksiklerini tamamlayın."),
        _category("health_follow_up", "Sağlık takibi", health_score, "Yalnız anonim sağlık uyum özeti.", "Gecikmiş muayeneleri planlayın."),
        _category("professional_workload", "Profesyonel iş yükü", workload_score, "Zorunlu, planlanan ve gerçekleşen dakika dengesi.", "İş yükünü yeniden dağıtın."),
        _category("audit_readiness", "Denetim hazırlığı", inspection_score, center.get("overall_label") or "Hazırlık özeti yok.", "Hazırlık engellerini kapatın."),
        _category("corrective_performance", "Düzeltici faaliyet performansı", corrective_score, _status_item(center, "capa").get("detail") or "DÖF özeti yok.", "Geciken DÖF kayıtlarını kapatın."),
    ]
    quality_score = round(sum(item["score"] for item in quality_categories) / len(quality_categories))
    return {
        "overall_score": overall,
        "status": status,
        "status_label": STATUS_LABELS[status],
        "categories": categories,
        "failed_checks": [item for item in categories if not item["passed"]],
        "critical_blockers": blockers,
        "recommended_actions": [item["recommended_action"] for item in categories if not item["passed"]],
        "quality_score": quality_score,
        "quality_categories": quality_categories,
        "calculation": "Görünür kategori puanı × görünür ağırlık / toplam ağırlık",
        "black_box": False,
    }


def _profile_base(
    profile: AuthorizedFirmProfile,
    company: Company,
    organization: OsgbOrganization | None,
    *,
    employee_count: int,
) -> dict[str, Any]:
    return {
        "id": profile.id,
        "osgb_id": profile.osgb_id,
        "osgb_name": organization.name if organization else None,
        "company_id": profile.company_id,
        "company_name": company.name,
        "firm_name": profile.firm_name,
        "is_active": bool(profile.is_active),
        "firm_type": profile.firm_type,
        "province": profile.province,
        "district": profile.district,
        "address": profile.address or company.address,
        "authorized_representative": profile.authorized_representative or company.authorized_person,
        "contact_email": profile.contact_email,
        "contact_phone": profile.contact_phone or company.phone,
        "employee_count": employee_count,
        "employee_count_declared": profile.employee_count_declared,
        "hazard_class": profile.hazard_class or company.hazard_class,
        "authorization_scope": profile.authorization_scope,
        "authorization_number": profile.authorization_number,
        "authorization_issue_date": _date_value(profile.authorization_issue_date),
        "authorization_start_date": _date_value(profile.authorization_start_date),
        "authorization_expiry_date": _date_value(profile.authorization_expiry_date),
        "authorization_validity": expiry_state(profile.authorization_expiry_date),
        "notes": profile.notes,
        "last_review_date": _date_value(profile.last_review_date),
        "review_state": profile.review_state,
        "record_notice": (
            "Bu kayıt İSG Suite iç kayıt bilgisidir; resmî makam doğrulaması anlamına gelmez."
            if profile.review_state == "internal_record"
            else "Yetkili yönetici tarafından uygulama içinde incelenmiştir; resmî makam doğrulaması değildir."
        ),
        "reviewed_at": _datetime_value(profile.reviewed_at),
        "onboarding": {
            "current_step": profile.onboarding_current_step,
            "completed_steps": _json_list(profile.onboarding_completed_steps),
            "status": profile.onboarding_status,
        },
        "created_at": _datetime_value(profile.created_at),
        "updated_at": _datetime_value(profile.updated_at),
    }


def build_profile_detail(db: Session, profile: AuthorizedFirmProfile, *, viewer=None) -> dict[str, Any]:
    company = db.get(Company, profile.company_id)
    if not company:
        raise ValueError("Yetkili firma bağlantılı işyeri bulunamadı.")
    organization = db.get(OsgbOrganization, profile.osgb_id)
    employee_count = int(
        db.scalar(
            select(func.count()).select_from(Employee).where(
                Employee.company_id == company.id,
                Employee.is_active.is_(True),
            )
        )
        or 0
    )
    today = date.today()
    documents = [
        _document_payload(item, today=today)
        for item in db.scalars(
            select(AuthorizedFirmDocument)
            .where(AuthorizedFirmDocument.profile_id == profile.id)
            .order_by(AuthorizedFirmDocument.mandatory.desc(), AuthorizedFirmDocument.title)
        ).all()
    ]
    assignments = list(
        db.scalars(
            select(WorkplaceAssignment)
            .where(
                WorkplaceAssignment.osgb_id == profile.osgb_id,
                WorkplaceAssignment.company_id == profile.company_id,
            )
            .order_by(WorkplaceAssignment.start_date.desc(), WorkplaceAssignment.id.desc())
        ).all()
    )
    professional_ids = {item.professional_id for item in assignments}
    professionals_raw = list(
        db.scalars(
            select(IsgProfessional)
            .where(
                IsgProfessional.osgb_id == profile.osgb_id,
                IsgProfessional.id.in_(professional_ids or {0}),
            )
            .order_by(IsgProfessional.full_name)
        ).all()
    )
    professionals = [
        evaluate_professional_compliance(db, item, company_id=profile.company_id, today=today)
        for item in professionals_raw
    ]
    contracts = list(
        db.scalars(
            select(ServiceContract)
            .where(
                ServiceContract.osgb_id == profile.osgb_id,
                ServiceContract.company_id == profile.company_id,
            )
            .order_by(ServiceContract.start_date.desc(), ServiceContract.id.desc())
        ).all()
    )
    visits = list(
        db.scalars(
            select(ServiceVisit)
            .where(
                ServiceVisit.osgb_id == profile.osgb_id,
                ServiceVisit.company_id == profile.company_id,
            )
            .order_by(ServiceVisit.visit_date.desc(), ServiceVisit.id.desc())
        ).all()
    )
    workplace = build_workplace_status(db, company, viewer=viewer)
    score = _build_scores(profile, documents, professionals, workplace, visits)
    history = []
    for item in db.scalars(
        select(ComplianceScoreSnapshot)
        .where(ComplianceScoreSnapshot.profile_id == profile.id)
        .order_by(ComplianceScoreSnapshot.created_at.desc(), ComplianceScoreSnapshot.id.desc())
        .limit(24)
    ).all():
        history.append(
            {
                "id": item.id,
                "overall_score": item.overall_score,
                "quality_score": item.quality_score,
                "status": item.status,
                "categories": _json_list(item.category_scores_json),
                "quality_categories": _json_list(item.quality_scores_json),
                "critical_blockers": _json_list(item.blockers_json),
                "created_at": _datetime_value(item.created_at),
            }
        )
    audits = [
        {
            "id": item.id,
            "action": item.action,
            "description": item.description,
            "user_id": item.user_id,
            "created_at": _datetime_value(item.created_at),
        }
        for item in db.scalars(
            select(AuditLog)
            .where(
                AuditLog.company_id == profile.company_id,
                AuditLog.entity_type.in_(("authorized_firm_profile", "authorized_firm_document", "professional_compliance")),
            )
            .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
            .limit(50)
        ).all()
    ]
    result = _profile_base(
        profile,
        company,
        organization,
        employee_count=employee_count,
    )
    result.update(
        {
            "documents": documents,
            "professionals": professionals,
            "assignments": [
                {
                    "id": item.id,
                    "professional_id": item.professional_id,
                    "professional_type": _enum_value(item.professional_type),
                    "start_date": _date_value(item.start_date),
                    "end_date": _date_value(item.end_date),
                    "status": _enum_value(item.status),
                    "required_minutes_monthly": int(item.required_minutes_monthly or 0),
                    "planned_minutes_monthly": int(item.planned_minutes_monthly or 0),
                    "actual_minutes_monthly": int(item.actual_minutes_monthly or 0),
                    "contract_covered": _contract_covers_assignment(db, item),
                }
                for item in assignments
            ],
            "contracts": [
                {
                    "id": item.id,
                    "contract_number": item.contract_number,
                    "start_date": _date_value(item.start_date),
                    "end_date": _date_value(item.end_date),
                    "status": item.status,
                    "validity": expiry_state(item.end_date, today=today),
                }
                for item in contracts
            ],
            "visits": [
                {
                    "id": item.id,
                    "professional_id": item.professional_id,
                    "visit_date": _date_value(item.visit_date),
                    "duration_minutes": int(item.duration_minutes or 0),
                    "subject": item.subject,
                    "status": _enum_value(item.status),
                }
                for item in visits[:100]
            ],
            "workplace_status": {
                "status_center": workplace.get("status_center"),
                "counts": workplace.get("counts"),
                "health": workplace.get("health"),
                "privacy": {"health_mode": "aggregate_only", "sensitive_fields_exposed": False},
            },
            "compliance_score": score,
            "score_history": history,
            "audit_history": audits,
        }
    )
    result["alerts"] = build_validity_alerts(result)
    center_items = ((result.get("workplace_status") or {}).get("status_center") or {}).get("items") or []
    center_by_code = {item.get("code"): item for item in center_items}
    onboarding_steps = [
        (1, "Firma ve işyeri bağlantısı", bool(result.get("firm_name") and result.get("company_id")), "Firma kartını ve bağlı işyerini doğrulayın."),
        (2, "Adres ve iletişim", bool(result.get("province") and result.get("district") and (result.get("contact_email") or result.get("contact_phone"))), "İl, ilçe ve iletişim bilgisini tamamlayın."),
        (3, "Yetki tarihleri", bool(result.get("authorization_start_date") and result.get("authorization_expiry_date")), "Yetki başlangıç ve bitiş tarihlerini girin."),
        (4, "Kapsam ve tehlike sınıfı", bool(result.get("authorization_scope") and result.get("hazard_class")), "Yetki kapsamı ve tehlike sınıfını tamamlayın."),
        (5, "Hizmet sözleşmesi", bool(result.get("contracts")), "Geçerli hizmet sözleşmesini oluşturun."),
        (6, "Profesyonel görevlendirmeleri", bool(result.get("assignments")), "Gerekli profesyonel görevlendirmelerini tamamlayın."),
        (7, "Profesyonel belge uygunluğu", bool(result.get("professionals")) and all(item.get("status") == "compliant" for item in result.get("professionals") or []), "Profesyonel belgelerini ve tarihlerini gözden geçirin."),
        (8, "Zorunlu firma belgeleri", bool(result.get("documents")) and all(item.get("validity", {}).get("code") in {"valid", "due_90", "due_60", "due_30"} for item in result.get("documents") or [] if item.get("mandatory")), "Zorunlu firma belgelerini yükleyin ve geçerliliklerini doğrulayın."),
        (9, "Risk değerlendirmesi", (center_by_code.get("risk_assessment") or {}).get("status") in {"completed", "due_soon", "informational"}, "Risk değerlendirmesi eksiklerini kapatın."),
        (10, "Eğitim ve sağlık takibi", all((center_by_code.get(code) or {}).get("status") in {"completed", "due_soon", "informational"} for code in ("training", "health_examinations")), "Eğitim ve anonim sağlık takip eksiklerini tamamlayın."),
        (11, "Yönetici incelemesi ve denetim hazırlığı", profile.review_state == "manually_reviewed" and not score.get("critical_blockers"), "Yönetici incelemesini yapın ve kritik engelleri kapatın."),
    ]
    result["onboarding"]["steps"] = [
        {"step": number, "title": title, "completed": bool(completed), "recommended_action": action}
        for number, title, completed, action in onboarding_steps
    ]
    result["automatic_task_checklist"] = [
        {
            "code": item.get("code"),
            "title": item.get("label"),
            "priority": "critical" if item.get("critical") else "normal",
            "detail": item.get("detail"),
            "recommended_action": item.get("recommended_action"),
        }
        for item in score.get("failed_checks") or []
    ]
    return result


def build_validity_alerts(detail: dict[str, Any]) -> list[dict[str, Any]]:
    alerts: list[dict[str, Any]] = []

    def add(code: str, title: str, validity: dict[str, Any], entity_type: str, entity_id: int | None, action: str) -> None:
        if validity.get("code") == "valid":
            return
        alerts.append(
            {
                "code": code,
                "title": title,
                "status": validity.get("code"),
                "severity": validity.get("severity"),
                "days_left": validity.get("days_left"),
                "entity_type": entity_type,
                "entity_id": entity_id,
                "suggested_action": action,
            }
        )

    add(
        "authorization",
        "Yetki kaydı geçerliliği",
        detail.get("authorization_validity") or {},
        "authorized_firm_profile",
        detail.get("id"),
        "Yetki tarihini ve bağlı belgeyi gözden geçirin.",
    )
    for item in detail.get("documents") or []:
        if item.get("mandatory") and item.get("is_active"):
            add(
                f"document:{item['id']}",
                item.get("title") or "Yetki belgesi",
                item.get("validity") or {},
                "authorized_firm_document",
                item.get("id"),
                "Belgeyi yükleyin, yenileyin veya tarihlerini doğrulayın.",
            )
    for item in detail.get("professionals") or []:
        add(
            f"professional:{item['professional_id']}",
            f"{item.get('full_name') or 'Profesyonel'} belge geçerliliği",
            item.get("validity") or {},
            "professional_compliance",
            item.get("professional_id"),
            "Profesyonel sertifikasını ve zorunlu belgeleri gözden geçirin.",
        )
    for item in detail.get("assignments") or []:
        validity = expiry_state(date.fromisoformat(item["end_date"]) if item.get("end_date") else None)
        if item.get("status") == "active":
            add(
                f"assignment:{item['id']}",
                "Görevlendirme bitişi",
                validity,
                "osgb_assignment",
                item.get("id"),
                "Görevlendirme süresini ve sözleşme kapsamını kontrol edin.",
            )
        if not item.get("contract_covered"):
            alerts.append(
                {
                    "code": f"assignment-contract:{item['id']}",
                    "title": "Görevlendirme sözleşme dışında",
                    "status": "invalid",
                    "severity": "critical",
                    "days_left": None,
                    "entity_type": "osgb_assignment",
                    "entity_id": item.get("id"),
                    "suggested_action": "Geçerli hizmet sözleşmesi oluşturun veya görevlendirme tarihini düzeltin.",
                }
            )
    alerts.sort(key=lambda item: (0 if item["severity"] == "critical" else 1 if item["severity"] == "warning" else 2, item["title"]))
    return alerts


def save_score_snapshot(db: Session, profile: AuthorizedFirmProfile, *, user=None) -> ComplianceScoreSnapshot:
    detail = build_profile_detail(db, profile, viewer=user)
    score = detail["compliance_score"]
    snapshot = ComplianceScoreSnapshot(
        profile_id=profile.id,
        osgb_id=profile.osgb_id,
        company_id=profile.company_id,
        overall_score=score["overall_score"],
        quality_score=score["quality_score"],
        status=score["status"],
        category_scores_json=json.dumps(score["categories"], ensure_ascii=False),
        quality_scores_json=json.dumps(score["quality_categories"], ensure_ascii=False),
        blockers_json=json.dumps(score["critical_blockers"], ensure_ascii=False),
        created_by_id=getattr(user, "id", None),
    )
    db.add(snapshot)
    db.flush()
    return snapshot


def list_profile_summaries(
    db: Session,
    *,
    osgb_id: int | None,
    viewer=None,
    query: str | None = None,
    province: str | None = None,
    district: str | None = None,
    active: bool | None = None,
    hazard_class: str | None = None,
    document_status: str | None = None,
    professional_id: int | None = None,
    professional_status: str | None = None,
    expiry_from: date | None = None,
    expiry_to: date | None = None,
    readiness: str | None = None,
    min_score: int | None = None,
) -> list[dict[str, Any]]:
    stmt = select(AuthorizedFirmProfile)
    if osgb_id is not None:
        stmt = stmt.where(AuthorizedFirmProfile.osgb_id == osgb_id)
    if query:
        needle = f"%{query.strip()}%"
        stmt = stmt.where(
            or_(
                AuthorizedFirmProfile.firm_name.ilike(needle),
                AuthorizedFirmProfile.authorization_number.ilike(needle),
            )
        )
    if province:
        stmt = stmt.where(func.lower(AuthorizedFirmProfile.province) == province.strip().lower())
    if district:
        stmt = stmt.where(func.lower(AuthorizedFirmProfile.district) == district.strip().lower())
    if active is not None:
        stmt = stmt.where(AuthorizedFirmProfile.is_active.is_(active))
    if hazard_class:
        stmt = stmt.where(func.lower(AuthorizedFirmProfile.hazard_class) == hazard_class.strip().lower())
    if expiry_from:
        stmt = stmt.where(AuthorizedFirmProfile.authorization_expiry_date >= expiry_from)
    if expiry_to:
        stmt = stmt.where(AuthorizedFirmProfile.authorization_expiry_date <= expiry_to)
    if professional_id:
        company_ids = select(WorkplaceAssignment.company_id).where(
            WorkplaceAssignment.professional_id == professional_id,
            WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
        )
        stmt = stmt.where(AuthorizedFirmProfile.company_id.in_(company_ids))
    profiles = list(db.scalars(stmt.order_by(AuthorizedFirmProfile.firm_name)).all())
    rows: list[dict[str, Any]] = []
    for profile in profiles:
        detail = build_profile_detail(db, profile, viewer=viewer)
        alerts = detail.get("alerts") or []
        score = detail["compliance_score"]
        document_states = {
            item["validity"]["code"]
            for item in detail.get("documents") or []
            if item.get("mandatory") and item.get("is_active")
        }
        if not document_states or "missing" in document_states:
            doc_state = "missing"
        elif "expired" in document_states:
            doc_state = "expired"
        elif document_states & {"due_30", "due_60", "due_90"}:
            doc_state = "expiring"
        else:
            doc_state = "valid"
        if document_status and document_status != doc_state:
            continue
        if professional_status and not any(
            item.get("status") == professional_status
            for item in detail.get("professionals") or []
        ):
            continue
        if readiness and readiness != score["status"]:
            continue
        if min_score is not None and score["overall_score"] < min_score:
            continue
        rows.append(
            {
                **{key: detail.get(key) for key in (
                    "id", "osgb_id", "osgb_name", "company_id", "company_name", "firm_name",
                    "is_active", "firm_type", "province", "district", "employee_count", "hazard_class",
                    "authorization_number", "authorization_start_date", "authorization_expiry_date",
                    "authorization_validity", "review_state", "record_notice",
                )},
                "document_status": doc_state,
                "alert_count": len(alerts),
                "professional_count": len(detail.get("professionals") or []),
                "workplace_count": 1,
                "compliance_score": score["overall_score"],
                "quality_score": score["quality_score"],
                "readiness_status": score["status"],
                "readiness_label": score["status_label"],
                "critical_blocker_count": len(score["critical_blockers"]),
            }
        )
    return rows


def build_dashboard_summary(db: Session, *, osgb_id: int, viewer=None) -> dict[str, Any]:
    rows = list_profile_summaries(db, osgb_id=osgb_id, viewer=viewer)
    scores = [row["compliance_score"] for row in rows]
    ranked = sorted(
        (
            {
                "profile_id": row["id"],
                "firm_name": row["firm_name"],
                "compliance_score": row["compliance_score"],
                "quality_score": row["quality_score"],
            }
            for row in rows
        ),
        key=lambda item: (-item["quality_score"], item["firm_name"]),
    )
    return {
        "total_firms": len(rows),
        "active_firms": sum(1 for row in rows if row["is_active"]),
        "expired_authorizations": sum(1 for row in rows if row["authorization_validity"]["code"] == "expired"),
        "expiring_30": sum(1 for row in rows if row["authorization_validity"]["code"] == "due_30"),
        "expiring_60": sum(1 for row in rows if row["authorization_validity"]["code"] == "due_60"),
        "expiring_90": sum(1 for row in rows if row["authorization_validity"]["code"] == "due_90"),
        "critical_firms": sum(1 for row in rows if row["readiness_status"] == "critical"),
        "ready_firms": sum(1 for row in rows if row["readiness_status"] == "ready"),
        "average_score": round(sum(scores) / len(scores)) if scores else 0,
        "firms": rows[:10],
        "quality_comparison": {
            "method": "Aynı OSGB içindeki firmaların görünür kalite kategorilerinin eşit ağırlıklı ortalaması",
            "black_box": False,
            "ranking": [dict(item, rank=index) for index, item in enumerate(ranked, start=1)],
        },
        "privacy": {"health_mode": "aggregate_only", "sensitive_fields_exposed": False},
    }


def build_osgb_comparison(db: Session, *, viewer=None) -> dict[str, Any]:
    """Yalnız platform yöneticisine sunulacak tenantlar arası anonim OSGB özeti."""
    organizations = list(
        db.scalars(select(OsgbOrganization).order_by(OsgbOrganization.name)).all()
    )
    rows: list[dict[str, Any]] = []
    for organization in organizations:
        firms = list_profile_summaries(db, osgb_id=organization.id, viewer=viewer)
        quality_scores = [int(item.get("quality_score") or 0) for item in firms]
        compliance_scores = [int(item.get("compliance_score") or 0) for item in firms]
        rows.append(
            {
                "osgb_id": organization.id,
                "osgb_name": organization.name,
                "firm_count": len(firms),
                "active_firm_count": sum(1 for item in firms if item.get("is_active")),
                "critical_firm_count": sum(1 for item in firms if item.get("readiness_status") == "critical"),
                "average_compliance_score": round(sum(compliance_scores) / len(compliance_scores)) if compliance_scores else 0,
                "average_quality_score": round(sum(quality_scores) / len(quality_scores)) if quality_scores else 0,
            }
        )
    ranked = sorted(
        rows,
        key=lambda item: (-item["average_quality_score"], -item["average_compliance_score"], item["osgb_name"]),
    )
    return {
        "method": "OSGB başına firma kalite ve uygunluk puanlarının aritmetik ortalaması; yalnız platform yöneticisi görür",
        "black_box": False,
        "items": [dict(item, rank=index) for index, item in enumerate(ranked, start=1)],
        "privacy": {"health_mode": "aggregate_only", "sensitive_fields_exposed": False},
    }


def rebuild_authorized_firm_notifications(db: Session, osgb_id: int) -> int:
    profiles = list(
        db.scalars(
            select(AuthorizedFirmProfile).where(
                AuthorizedFirmProfile.osgb_id == osgb_id,
                AuthorizedFirmProfile.is_active.is_(True),
            )
        ).all()
    )
    notifications: list[Notification] = []
    for profile in profiles:
        detail = build_profile_detail(db, profile)
        for alert in detail.get("alerts") or []:
            if alert["entity_type"] not in {
                "authorized_firm_profile",
                "authorized_firm_document",
                "professional_compliance",
            }:
                continue
            ntype = NotificationType.CRITICAL if alert["severity"] == "critical" else NotificationType.WARNING
            notifications.append(
                Notification(
                    company_id=profile.company_id,
                    type=ntype,
                    title=(alert["title"] or "Yetkili firma uyarısı")[:220],
                    message=(
                        f"{profile.firm_name}: {alert['status']}. {alert['suggested_action']}"
                    )[:1200],
                    entity_type=alert["entity_type"],
                    entity_id=str(alert["entity_id"] or profile.id),
                )
            )
    db.add_all(notifications)
    return len(notifications)
