"""Eyas — işyeri (Company) bazlı belge kataloğu ve onaycı önerileri."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.company_access import link_user_to_professional
from app.models.entities import (
    AnnualPlanItem,
    Company,
    DocumentRecord,
    EmergencyPlan,
    HealthRecord,
    IsgProfessional,
    PpeAssignment,
    ProfessionalType,
    RiskAssessment,
    TrainingSession,
    TrainingStatus,
    User,
    UserRole,
    WorkplaceMembership,
)
from app.services.assigned_team import assigned_team

KIND_LABELS = {
    "risk": "Risk Analizi / Değerlendirme Raporu",
    "training": "Eğitim",
    "health": "Sağlık Raporu",
    "emergency": "Acil Durum Planı",
    "ppe": "KKD Teslim",
    "annual_plan": "Yıllık Çalışma Planı",
    "document": "Arşiv Belgesi",
}


def _item(
    *,
    kind: str,
    source_key: str,
    title: str,
    readiness: str,
    readiness_detail: str,
    download_path: str | None = None,
    source_id: int | None = None,
    document_record_id: int | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "kind_label": KIND_LABELS.get(kind, kind),
        "source_key": source_key,
        "title": title,
        "source_id": source_id,
        "document_record_id": document_record_id,
        "readiness": readiness,
        "readiness_detail": readiness_detail,
        "download_path": download_path,
        "selectable": readiness == "ready",
    }


def list_approval_documents(db: Session, company_id: int) -> dict[str, Any]:
    """İşyerindeki onaylanabilir belgeler — hazır değilse seçilemez."""
    company = db.get(Company, company_id)
    if not company:
        return {"company_id": company_id, "company_name": None, "items": [], "summary": {}}

    items: list[dict[str, Any]] = []

    risk_n = db.scalar(
        select(func.count()).select_from(RiskAssessment).where(RiskAssessment.company_id == company_id)
    ) or 0
    if risk_n > 0:
        items.append(
            _item(
                kind="risk",
                source_key="risk:report",
                title=f"{company.name} — Risk Değerlendirme Raporu",
                readiness="ready",
                readiness_detail=f"{risk_n} risk kaydı mevcut",
                download_path=f"/api/v1/risks/report.pdf?company_id={company_id}",
            )
        )
    else:
        items.append(
            _item(
                kind="risk",
                source_key="risk:report",
                title=f"{company.name} — Risk Değerlendirme Raporu",
                readiness="missing",
                readiness_detail="Rapor hazır değil: risk kaydı yok",
                download_path=f"/api/v1/risks/report.pdf?company_id={company_id}",
            )
        )

    training_rows = db.execute(
        select(
            TrainingSession.id,
            TrainingSession.title,
            TrainingSession.start_date,
            TrainingSession.status,
            TrainingSession.attendance_verified,
        )
        .where(TrainingSession.company_id == company_id)
        .order_by(TrainingSession.id.desc())
        .limit(30)
    ).all()
    if not training_rows:
        items.append(
            _item(
                kind="training",
                source_key="training:none",
                title="Eğitim belgesi",
                readiness="missing",
                readiness_detail="Rapor hazır değil: eğitim kaydı yok",
            )
        )
    else:
        for tid, title, start_date, status, attendance_verified in training_rows:
            status_val = status.value if hasattr(status, "value") else status
            ready = status == TrainingStatus.COMPLETED or status_val == TrainingStatus.COMPLETED.value or bool(
                attendance_verified
            )
            items.append(
                _item(
                    kind="training",
                    source_key=f"training:{tid}",
                    title=f"{title} ({start_date})",
                    readiness="ready" if ready else "partial",
                    readiness_detail=f"Durum: {status_val}" + ("; yoklama doğrulandı" if attendance_verified else ""),
                    download_path=f"/api/v1/trainings/{tid}/attendance.pdf",
                    source_id=tid,
                )
            )

    health_rows = list(
        db.scalars(
            select(HealthRecord)
            .where(HealthRecord.company_id == company_id)
            .order_by(HealthRecord.id.desc())
            .limit(30)
        ).all()
    )
    if not health_rows:
        items.append(
            _item(
                kind="health",
                source_key="health:none",
                title="Sağlık raporu",
                readiness="missing",
                readiness_detail="Rapor hazır değil: sağlık kaydı yok",
            )
        )
    else:
        for h in health_rows:
            has_file = bool(h.report_storage_path)
            items.append(
                _item(
                    kind="health",
                    source_key=f"health:{h.id}",
                    title=f"Sağlık kaydı #{h.id} ({h.examination_date})",
                    readiness="ready" if has_file else "partial",
                    readiness_detail="Dosya yüklü" if has_file else "Kayıt var; rapor dosyası yok",
                    download_path=f"/api/v1/health/{h.id}/report" if has_file else None,
                    source_id=h.id,
                )
            )

    plans = list(
        db.scalars(
            select(EmergencyPlan)
            .where(EmergencyPlan.company_id == company_id, EmergencyPlan.is_active.is_(True))
            .order_by(EmergencyPlan.id.desc())
            .limit(20)
        ).all()
    )
    if not plans:
        items.append(
            _item(
                kind="emergency",
                source_key="emergency:none",
                title="Acil durum planı",
                readiness="missing",
                readiness_detail="Rapor hazır değil: acil durum planı yok",
            )
        )
    else:
        for p in plans:
            ready = bool(p.kroki_storage_path or p.document_id or p.scenario_summary)
            items.append(
                _item(
                    kind="emergency",
                    source_key=f"emergency:{p.id}",
                    title=f"{p.title} (Rev {p.revision_no})",
                    readiness="ready" if ready else "partial",
                    readiness_detail="Plan içeriği mevcut" if ready else "Plan kaydı eksik içerik",
                    source_id=p.id,
                    document_record_id=p.document_id,
                )
            )

    ppe_n = db.scalar(
        select(func.count()).select_from(PpeAssignment).where(PpeAssignment.company_id == company_id)
    ) or 0
    items.append(
        _item(
            kind="ppe",
            source_key="ppe:list",
            title=f"{company.name} — KKD Teslim Listesi",
            readiness="ready" if ppe_n > 0 else "missing",
            readiness_detail=f"{ppe_n} KKD teslim kaydı" if ppe_n else "Rapor hazır değil: KKD kaydı yok",
            download_path=f"/api/v1/ppe/export.xlsx?company_id={company_id}",
        )
    )

    annual_n = db.scalar(
        select(func.count())
        .select_from(AnnualPlanItem)
        .where(AnnualPlanItem.company_id == company_id, AnnualPlanItem.deleted_at.is_(None))
    ) or 0
    items.append(
        _item(
            kind="annual_plan",
            source_key="annual_plan:export",
            title=f"{company.name} — Yıllık Çalışma Planı",
            readiness="ready" if annual_n > 0 else "missing",
            readiness_detail=f"{annual_n} plan kalemi" if annual_n else "Rapor hazır değil: yıllık plan yok",
            download_path=f"/api/v1/annual-plans/export.pdf?company_id={company_id}",
        )
    )

    docs = list(
        db.scalars(
            select(DocumentRecord)
            .where(DocumentRecord.company_id == company_id, DocumentRecord.is_active.is_(True))
            .order_by(DocumentRecord.id.desc())
            .limit(40)
        ).all()
    )
    for d in docs:
        stored = (d.description or "").find("[stored:") >= 0
        items.append(
            _item(
                kind="document",
                source_key=f"document:{d.id}",
                title=d.title,
                readiness="ready" if stored else "partial",
                readiness_detail="Dosya arşivde" if stored else "Kayıt var; dosya yok",
                download_path=f"/api/v1/files/documents/{d.id}/download" if stored else None,
                source_id=d.id,
                document_record_id=d.id,
            )
        )

    summary = {
        "ready": sum(1 for i in items if i["readiness"] == "ready"),
        "partial": sum(1 for i in items if i["readiness"] == "partial"),
        "missing": sum(1 for i in items if i["readiness"] == "missing"),
    }
    return {
        "company_id": company_id,
        "company_name": company.name,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "items": items,
        "summary": summary,
    }


def resolve_document(db: Session, company_id: int, source_key: str) -> dict[str, Any]:
    catalog = list_approval_documents(db, company_id)
    for item in catalog["items"]:
        if item["source_key"] == source_key:
            return item
    raise KeyError(source_key)


def suggested_assignees(db: Session, company_id: int) -> dict[str, Any]:
    """İşyeri görevlendirme + işveren/vekil hesap önerisi."""
    company = db.get(Company, company_id)
    team = assigned_team(db, company_id)

    def user_for_pro(pro_blob: dict | None) -> User | None:
        if not pro_blob:
            return None
        pro = db.get(IsgProfessional, pro_blob["professional_id"])
        if not pro:
            return None
        return link_user_to_professional(db, pro)

    uzman_user = user_for_pro(team.get(ProfessionalType.SAFETY_SPECIALIST.value))
    hekim_user = user_for_pro(team.get(ProfessionalType.WORKPLACE_PHYSICIAN.value))

    # İşveren / vekil: önce membership company_admin, sonra osgb company_admin
    employer_cands: list[User] = []
    mem_user_ids = list(
        db.scalars(
            select(WorkplaceMembership.user_id).where(
                WorkplaceMembership.company_id == company_id,
                WorkplaceMembership.is_active.is_(True),
            )
        ).all()
    )
    if mem_user_ids:
        for u in db.scalars(
            select(User).where(
                User.id.in_(mem_user_ids),
                User.is_active.is_(True),
                User.role == UserRole.COMPANY_ADMIN,
            )
        ).all():
            employer_cands.append(u)
    if company and company.osgb_id and not employer_cands:
        for u in db.scalars(
            select(User)
            .where(
                User.osgb_id == company.osgb_id,
                User.role == UserRole.COMPANY_ADMIN,
                User.is_active.is_(True),
            )
            .order_by(User.id)
            .limit(10)
        ).all():
            employer_cands.append(u)

    def step(order: int, role_key: str, label: str, user: User | None, source: str, warnings: list[str]):
        alts = []
        if user:
            alts.append(
                {
                    "user_id": user.id,
                    "full_name": user.full_name,
                    "role": user.role.value if hasattr(user.role, "value") else str(user.role),
                    "mfa_enabled": bool(user.mfa_enabled),
                }
            )
        return {
            "step_order": order,
            "role_key": role_key,
            "role_label": label,
            "suggested_user_id": user.id if user else None,
            "suggested_user_name": user.full_name if user else None,
            "suggested_source": source,
            "alternatives": alts,
            "warnings": warnings,
        }

    steps = [
        step(
            1,
            "safety_specialist",
            "İş Güvenliği Uzmanı",
            uzman_user,
            "workplace_assignment",
            [] if uzman_user else ["Bu işyerinde aktif İSG uzmanı hesabı bulunamadı"],
        ),
        step(
            2,
            "workplace_physician",
            "İşyeri Hekimi",
            hekim_user,
            "workplace_assignment",
            [] if hekim_user else ["Bu işyerinde aktif işyeri hekimi hesabı bulunamadı"],
        ),
        step(
            3,
            "employer_representative",
            "İşveren / vekili",
            employer_cands[0] if employer_cands else None,
            "company_admin_user",
            (
                ([] if employer_cands else ["İşveren / vekil kullanıcı hesabı bulunamadı"])
                + (
                    [f"Yetkili kişi metni: {company.authorized_person}"]
                    if company and company.authorized_person
                    else []
                )
            ),
        ),
    ]
    if employer_cands and len(employer_cands) > 1:
        steps[2]["alternatives"] = [
            {
                "user_id": u.id,
                "full_name": u.full_name,
                "role": u.role.value if hasattr(u.role, "value") else str(u.role),
                "mfa_enabled": bool(u.mfa_enabled),
            }
            for u in employer_cands
        ]

    return {
        "company_id": company_id,
        "company_name": company.name if company else None,
        "authorized_person_text": company.authorized_person if company else None,
        "legal_notice": (
            "Dijital Onay — nitelikli e-imza değildir. "
            "Sıra: İş Güvenliği Uzmanı → İşyeri Hekimi → İşveren / vekili."
        ),
        "steps": steps,
        "team": team,
    }
