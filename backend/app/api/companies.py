from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import delete, inspect, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.company_access import companies_query_for_user, ensure_company_access
from app.api.deps import (
    get_current_user,
    reject_company_bound_admin_from_osgb_internal,
    require_roles,
)
from app.core.config import settings
from app.core.database import get_db
from app.models.entities import (
    AnnualPlanEvalCapa,
    AnnualPlanEvalEvidence,
    AnnualPlanEvalRevision,
    AnnualPlanEvaluation,
    AnnualPlanEvaluationItem,
    AnnualPlanItem,
    AnnualPlanUnplannedActivity,
    AuditLog,
    Branch,
    Company,
    CompanySubscription,
    DocumentApproval,
    DocumentRecord,
    DrillPhoto,
    DrillRecord,
    EisaArchiveRecord,
    EisaErrorReport,
    ESignArtifact,
    ESignRequest,
    ESignatureAuditEvent,
    ESignatureRequest,
    EyasEvent,
    EyasStep,
    EyasWorkflow,
    EmergencyPlan,
    EmergencyPlanFloor,
    EmergencyTeam,
    EmergencyTeamAssignment,
    EmergencyTeamTraining,
    EmergencyTeamType,
    Employee,
    FinanceTransaction,
    HealthRecord,
    IncidentDof,
    IncidentEvent,
    IncidentRootCause,
    IsgRecord,
    Notification,
    LegalAcceptance,
    ChemicalProduct,
    OhsCommitteeMember,
    OhsCommitteeMeeting,
    PeriodicControl,
    PpeAssignment,
    PpeAssignmentPhoto,
    PpeInventoryItem,
    PpeInventoryMovement,
    RiskAssessment,
    RiskDof,
    RiskMedia,
    ServiceContract,
    ServiceVisit,
    SiteQrSession,
    TrainingParticipant,
    TrainingSession,
    User,
    UserRole,
    WorkplaceAssignment,
    WorkplaceMeasurement,
    WorkplaceMembership,
    WorkplaceDepartment,
)
from app.models.entities import OsgbOrganization
from app.models.field_inspection import (
    FieldHazard,
    FieldInspection,
    FieldInspectionAction,
    FieldInspectionAnnotation,
    FieldInspectionArea,
    FieldInspectionEquipment,
    FieldInspectionFinding,
    FieldInspectionLegalReference,
    FieldInspectionPhoto,
    FieldInspectionSite,
)
from app.schemas.company import CompanyCreate, CompanyCreateResponse, CompanyResponse, CompanyUpdate
from app.services.company_overview import build_company_overview
from app.services.capacity_engine import sync_company_service_requirements
from app.services.employer_oversight import build_employer_oversight
from app.services.workplace_status import build_workplace_status
from app.services.workplace_status_reports import (
    build_workplace_status_excel,
    build_workplace_status_pdf,
)
from app.services.site_verify import (
    build_ephemeral_qr_payload,
    build_qr_payload,
    create_ephemeral_session,
    ensure_company_site_verify_code,
    generate_site_verify_code,
)

router = APIRouter(prefix="/companies", tags=["Firmalar"])


def _apply_nace_classification(
    data: dict, *, existing_nace_code: str | None = None
) -> None:
    """Make the stored company hazard class authoritative for its NACE code."""
    raw = data.get("nace_code") if "nace_code" in data else existing_nace_code
    raw = str(raw or "").strip()
    if not raw:
        # An explicitly cleared NACE must not leave a stale derived class.
        if "nace_code" in data:
            data["hazard_class"] = None
        return

    from app.services.training_nace_classification import resolve_exact_nace

    try:
        classification = resolve_exact_nace(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=422,
            detail="Geçerli ve tam bir NACE kodu girilmelidir; tehlike sınıfı NACE'den belirlenir.",
        ) from exc
    data["nace_code"] = classification.nace_code
    data["hazard_class"] = classification.hazard_class


def _default_osgb_id(db: Session) -> int | None:
    return db.scalar(select(OsgbOrganization.id).order_by(OsgbOrganization.id).limit(1))


def _company_name_taken(
    db: Session,
    name: str,
    osgb_id: int | None,
    *,
    exclude_id: int | None = None,
) -> bool:
    """Aynı OSGB içinde ad çakışması (P1-05: global unique değil)."""
    stmt = select(Company.id).where(Company.name == name)
    if osgb_id is None:
        stmt = stmt.where(Company.osgb_id.is_(None))
    else:
        stmt = stmt.where(Company.osgb_id == osgb_id)
    if exclude_id is not None:
        stmt = stmt.where(Company.id != exclude_id)
    return db.scalar(stmt.limit(1)) is not None


def _ids(db: Session, model, company_id: int) -> list[int]:
    return list(db.scalars(select(model.id).where(model.company_id == company_id)).all())


def _purge_company_data(db: Session, company_id: int) -> None:
    """Firma ve bağlı tüm operasyonel kayıtları kalıcı siler (kullanıcıları ayırır)."""
    # Görsel saha denetimi bounded context'i: şirket silinirse yeni tabloların
    # çocukları da FK sırasıyla temizlenir. Bu blok mevcut /risks kayıtlarına
    # dokunmaz; migration henüz uygulanmamış eski kurulumlarda da mevcut
    # şirket silme akışını bozmaz.
    if inspect(db.get_bind()).has_table("field_inspections"):
        visual_inspection_ids = _ids(db, FieldInspection, company_id)
        visual_finding_ids = list(
            db.scalars(
                select(FieldInspectionFinding.id).where(
                    FieldInspectionFinding.inspection_id.in_(visual_inspection_ids)
                )
            ).all()
        ) if visual_inspection_ids else []
        if visual_finding_ids:
            db.execute(delete(FieldInspectionLegalReference).where(FieldInspectionLegalReference.finding_id.in_(visual_finding_ids)))
        if visual_inspection_ids:
            db.execute(delete(FieldInspectionAnnotation).where(FieldInspectionAnnotation.inspection_id.in_(visual_inspection_ids)))
            db.execute(delete(FieldInspectionAction).where(FieldInspectionAction.inspection_id.in_(visual_inspection_ids)))
            db.execute(delete(FieldInspectionFinding).where(FieldInspectionFinding.inspection_id.in_(visual_inspection_ids)))
            db.execute(delete(FieldInspectionPhoto).where(FieldInspectionPhoto.inspection_id.in_(visual_inspection_ids)))
            db.execute(delete(FieldInspection).where(FieldInspection.id.in_(visual_inspection_ids)))
        db.execute(delete(FieldInspectionEquipment).where(FieldInspectionEquipment.company_id == company_id))
        db.execute(delete(FieldInspectionArea).where(FieldInspectionArea.company_id == company_id))
        db.execute(delete(FieldInspectionSite).where(FieldInspectionSite.company_id == company_id))
        db.execute(delete(FieldHazard).where(FieldHazard.company_id == company_id))

    risk_ids = _ids(db, RiskAssessment, company_id)
    if risk_ids:
        db.execute(delete(RiskMedia).where(RiskMedia.risk_id.in_(risk_ids)))
        db.execute(delete(RiskDof).where(RiskDof.risk_id.in_(risk_ids)))
        db.execute(delete(RiskAssessment).where(RiskAssessment.id.in_(risk_ids)))

    incident_ids = _ids(db, IncidentEvent, company_id)
    if incident_ids:
        db.execute(delete(IncidentRootCause).where(IncidentRootCause.incident_id.in_(incident_ids)))
        db.execute(delete(IncidentDof).where(IncidentDof.incident_id.in_(incident_ids)))
        db.execute(delete(IncidentEvent).where(IncidentEvent.id.in_(incident_ids)))

    ppe_ids = _ids(db, PpeAssignment, company_id)
    # KKD stok hareketleri ve kartları, zimmet/şirket silinmeden önce temizlenir.
    # PostgreSQL CASCADE bunu güvenceye alsa da SQLite ve eski kurulumlarda
    # açık temizlik, şirket silme akışını tutarlı tutar.
    db.execute(delete(PpeInventoryMovement).where(PpeInventoryMovement.company_id == company_id))
    db.execute(delete(PpeInventoryItem).where(PpeInventoryItem.company_id == company_id))
    if ppe_ids:
        db.execute(delete(PpeAssignmentPhoto).where(PpeAssignmentPhoto.assignment_id.in_(ppe_ids)))
        db.execute(delete(PpeAssignment).where(PpeAssignment.id.in_(ppe_ids)))

    training_ids = _ids(db, TrainingSession, company_id)
    if training_ids:
        db.execute(delete(TrainingParticipant).where(TrainingParticipant.training_id.in_(training_ids)))
        db.execute(delete(TrainingSession).where(TrainingSession.id.in_(training_ids)))

    # Acil durum ekipleri (emergency_teams → companies FK)
    assign_ids = _ids(db, EmergencyTeamAssignment, company_id)
    if assign_ids:
        db.execute(
            delete(EmergencyTeamTraining).where(EmergencyTeamTraining.assignment_id.in_(assign_ids))
        )
        db.execute(delete(EmergencyTeamAssignment).where(EmergencyTeamAssignment.id.in_(assign_ids)))
    db.execute(delete(EmergencyTeam).where(EmergencyTeam.company_id == company_id))
    db.execute(
        delete(EmergencyTeamType).where(
            EmergencyTeamType.company_id == company_id,
            EmergencyTeamType.is_system.is_(False),
        )
    )
    db.execute(delete(EmergencyPlanFloor).where(EmergencyPlanFloor.company_id == company_id))
    db.execute(delete(EmergencyPlan).where(EmergencyPlan.company_id == company_id))
    db.execute(delete(SiteQrSession).where(SiteQrSession.company_id == company_id))

    # 6331 uyum sicilleri / İSG Kurulu kayıtları. Bunlar doğrudan companies FK
    # tuttuğu için firma veya OSGB kalıcı silinmeden önce temizlenmelidir.
    db.execute(delete(OhsCommitteeMeeting).where(OhsCommitteeMeeting.company_id == company_id))
    db.execute(delete(OhsCommitteeMember).where(OhsCommitteeMember.company_id == company_id))

    # Belge onay / e-imza / Eyas zincirleri: çocuk kayıtlar önce silinir.
    db.execute(delete(EyasEvent).where(EyasEvent.company_id == company_id))
    db.execute(delete(EyasStep).where(EyasStep.company_id == company_id))
    db.execute(delete(EyasWorkflow).where(EyasWorkflow.company_id == company_id))
    db.execute(
        delete(ESignatureAuditEvent).where(ESignatureAuditEvent.company_id == company_id)
    )
    db.execute(delete(ESignArtifact).where(ESignArtifact.company_id == company_id))
    db.execute(delete(ESignRequest).where(ESignRequest.company_id == company_id))
    db.execute(delete(ESignatureRequest).where(ESignatureRequest.company_id == company_id))
    db.execute(delete(DocumentApproval).where(DocumentApproval.company_id == company_id))

    # 6331 kapsamındaki diğer doğrudan firma sicilleri.
    db.execute(delete(PeriodicControl).where(PeriodicControl.company_id == company_id))
    db.execute(
        delete(WorkplaceMeasurement).where(WorkplaceMeasurement.company_id == company_id)
    )
    db.execute(delete(WorkplaceMembership).where(WorkplaceMembership.company_id == company_id))

    # Tatbikat
    drill_ids = _ids(db, DrillRecord, company_id)
    if drill_ids:
        db.execute(delete(DrillPhoto).where(DrillPhoto.drill_id.in_(drill_ids)))
        db.execute(delete(DrillRecord).where(DrillRecord.id.in_(drill_ids)))

    # Yıllık plan değerlendirme (plan_item FK önce temizlenmeli)
    eval_ids = _ids(db, AnnualPlanEvaluation, company_id)
    if eval_ids:
        item_ids = list(
            db.scalars(
                select(AnnualPlanEvaluationItem.id).where(
                    AnnualPlanEvaluationItem.evaluation_id.in_(eval_ids)
                )
            ).all()
        )
        if item_ids:
            db.execute(
                delete(AnnualPlanEvalEvidence).where(
                    AnnualPlanEvalEvidence.evaluation_item_id.in_(item_ids)
                )
            )
        db.execute(delete(AnnualPlanEvalCapa).where(AnnualPlanEvalCapa.evaluation_id.in_(eval_ids)))
        db.execute(
            delete(AnnualPlanEvalRevision).where(AnnualPlanEvalRevision.evaluation_id.in_(eval_ids))
        )
        db.execute(
            delete(AnnualPlanUnplannedActivity).where(
                AnnualPlanUnplannedActivity.evaluation_id.in_(eval_ids)
            )
        )
        db.execute(
            delete(AnnualPlanEvaluationItem).where(
                AnnualPlanEvaluationItem.evaluation_id.in_(eval_ids)
            )
        )
        db.execute(delete(AnnualPlanEvaluation).where(AnnualPlanEvaluation.id.in_(eval_ids)))
    db.execute(
        delete(AnnualPlanEvaluationItem).where(AnnualPlanEvaluationItem.company_id == company_id)
    )
    db.execute(
        delete(AnnualPlanUnplannedActivity).where(
            AnnualPlanUnplannedActivity.company_id == company_id
        )
    )

    emp_ids = list(db.scalars(select(Employee.id).where(Employee.company_id == company_id)).all())
    if emp_ids:
        # Başka firmaya taşınmış eğitim katılımı kalmış olabilir
        db.execute(delete(TrainingParticipant).where(TrainingParticipant.employee_id.in_(emp_ids)))
        db.execute(delete(HealthRecord).where(HealthRecord.employee_id.in_(emp_ids)))
        db.execute(delete(PpeAssignment).where(PpeAssignment.employee_id.in_(emp_ids)))
        db.execute(
            delete(EmergencyTeamAssignment).where(EmergencyTeamAssignment.employee_id.in_(emp_ids))
        )

    db.execute(delete(HealthRecord).where(HealthRecord.company_id == company_id))
    db.execute(delete(IsgRecord).where(IsgRecord.company_id == company_id))
    db.execute(delete(ChemicalProduct).where(ChemicalProduct.company_id == company_id))
    db.execute(delete(DocumentRecord).where(DocumentRecord.company_id == company_id))
    db.execute(delete(AnnualPlanItem).where(AnnualPlanItem.company_id == company_id))
    db.execute(delete(ServiceVisit).where(ServiceVisit.company_id == company_id))
    db.execute(delete(WorkplaceAssignment).where(WorkplaceAssignment.company_id == company_id))
    db.execute(delete(ServiceContract).where(ServiceContract.company_id == company_id))
    db.execute(delete(CompanySubscription).where(CompanySubscription.company_id == company_id))
    db.execute(delete(WorkplaceDepartment).where(WorkplaceDepartment.company_id == company_id))
    db.execute(delete(Employee).where(Employee.company_id == company_id))
    db.execute(delete(Branch).where(Branch.company_id == company_id))

    # Nullable bağlar: ayır
    db.execute(update(User).where(User.company_id == company_id).values(company_id=None))
    db.execute(update(AuditLog).where(AuditLog.company_id == company_id).values(company_id=None))
    db.execute(update(Notification).where(Notification.company_id == company_id).values(company_id=None))
    db.execute(
        update(LegalAcceptance)
        .where(LegalAcceptance.company_id == company_id)
        .values(company_id=None)
    )
    db.execute(
        update(FinanceTransaction)
        .where(FinanceTransaction.company_id == company_id)
        .values(company_id=None)
    )
    db.execute(
        update(EisaErrorReport).where(EisaErrorReport.company_id == company_id).values(company_id=None)
    )
    db.execute(
        update(EisaArchiveRecord)
        .where(EisaArchiveRecord.company_id == company_id)
        .values(company_id=None)
    )


@router.get("", response_model=list[CompanyResponse])
def list_companies(
    q: str | None = Query(None),
    active: bool | None = Query(None, description="True=yalnız aktif, False=yalnız pasif, None=hepsi (yönetici)"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Company).order_by(Company.name)
    # Saha / firma kullanıcıları varsayılan yalnız aktif; global admin hepsini görür
    if active is not None:
        stmt = stmt.where(Company.is_active.is_(active))
    elif user.role != UserRole.GLOBAL_ADMIN:
        stmt = stmt.where(Company.is_active.is_(True))
    scope = companies_query_for_user(db, user)
    if scope is not None:
        stmt = stmt.where(scope)
    if q:
        stmt = stmt.where(
            or_(
                Company.name.ilike(f"%{q}%"),
                Company.sgk_registry_no.ilike(f"%{q}%"),
                Company.address.ilike(f"%{q}%"),
                Company.phone.ilike(f"%{q}%"),
                Company.authorized_person.ilike(f"%{q}%"),
            )
        )
    return list(db.scalars(stmt).all())


@router.get("/{company_id}", response_model=CompanyResponse)
def get_company(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_company_access(db, user, company_id)
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
    return obj


@router.get("/{company_id}/overview")
def company_overview(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    # Müşteri 360 özeti OSGB sözleşme ve finans verilerini de içerir. Tek
    # işyerine bağlı işveren / İK hesabı kendi firması için dahi bu OSGB-içi
    # ticari görünüme giremez; operasyonel işyeri durumu ayrı endpointtedir.
    if user.role == UserRole.COMPANY_ADMIN and user.company_id:
        raise HTTPException(403, "Bu görünüm yalnızca OSGB yönetimine açıktır.")
    ensure_company_access(db, user, company_id)
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
    return build_company_overview(db, obj)


@router.get("/{company_id}/status")
def workplace_status(
    company_id: int,
    response: Response,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Tek işyerinin birleşik, gerçek zamanlı durum merkezi.

    OSGB yöneticisi kendi OSGB'sini; işveren kendi işyerini; uzman, hekim ve
    DSP yalnız aktif görevlendirildiği işyerlerini görebilir.
    """
    ensure_company_access(db, user, company_id)
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
    response.headers["Cache-Control"] = "no-store"
    return build_workplace_status(db, obj, viewer=user)


@router.get("/{company_id}/status/report.xlsx")
def workplace_status_report_excel(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_company_access(db, user, company_id)
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
    data = build_workplace_status_excel(build_workplace_status(db, obj, viewer=user))
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="workplace-status-{company_id}.xlsx"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{company_id}/status/report.pdf")
def workplace_status_report_pdf(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ensure_company_access(db, user, company_id)
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
    data = build_workplace_status_pdf(build_workplace_status(db, obj, viewer=user))
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="workplace-status-{company_id}.pdf"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get("/{company_id}/employer-oversight")
def company_employer_oversight(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    """İşveren / işyeri denetim paneli — özet + işveren adımı onayı."""
    ensure_company_access(db, user, company_id)
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
    return build_employer_oversight(db, obj, viewer=user)


@router.post("/{company_id}/kiosk-login/reset")
def reset_company_kiosk_login(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    """Kiosk şifresini yalnızca bilinçli sıfırlar; her firma kaydında yenilenmez."""
    if user.role == UserRole.COMPANY_ADMIN and user.company_id:
        raise HTTPException(403, "İşyeri kiosk hesabı şifre sıfırlayamaz.")
    ensure_company_access(db, user, company_id)
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
    from app.services.osgb_admin import provision_workplace_kiosk_login

    kiosk_user, plaintext, created = provision_workplace_kiosk_login(db, obj, reset_password=True)
    db.commit()
    if not plaintext:
        raise HTTPException(500, "Şifre üretilemedi.")
    return {
        "user_id": kiosk_user.id,
        "email": kiosk_user.email,
        "full_name": kiosk_user.full_name,
        "password": plaintext,
        "temporary_password": plaintext,
        "created": created,
        "message": "Kiosk şifresi yenilendi. Eski şifre artık geçersiz. İşyerine yeni şifreyi iletin.",
    }


@router.get("/{company_id}/site-qr")
def company_site_qr(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    """İşyeri saha QR kodu — OSGB yazdırma / paylaşım."""
    ensure_company_access(db, user, company_id)
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
    had_code = bool((obj.site_verify_code or "").strip())
    ensure_company_site_verify_code(db, obj)
    if not had_code:
        db.commit()
        db.refresh(obj)
    payload = build_qr_payload(obj.id, obj.site_verify_code)
    return {
        "company_id": obj.id,
        "company_name": obj.name,
        "site_verify_code": obj.site_verify_code,
        "qr_payload": payload,
    }


@router.post("/{company_id}/site-qr/regenerate")
def regenerate_company_site_qr(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    ensure_company_access(db, user, company_id)
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
    obj.site_verify_code = generate_site_verify_code()
    db.commit()
    db.refresh(obj)
    payload = build_qr_payload(obj.id, obj.site_verify_code)
    return {
        "company_id": obj.id,
        "company_name": obj.name,
        "site_verify_code": obj.site_verify_code,
        "qr_payload": payload,
    }


@router.post("/{company_id}/site-qr/ephemeral")
def create_company_ephemeral_site_qr(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    """Geçici saha QR (TTL). Kiosk giriş/çıkış aynı dönem kodunu yeniden kullanabilir; yenilemede eski iptal."""
    ensure_company_access(db, user, company_id)
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
    row = create_ephemeral_session(db, company_id=obj.id, created_by_id=user.id)
    db.commit()
    db.refresh(row)
    payload = build_ephemeral_qr_payload(obj.id, row.token)
    return {
        "company_id": obj.id,
        "company_name": obj.name,
        "kind": "ephemeral",
        "token": row.token,
        "qr_payload": payload,
        "expires_at": row.expires_at.isoformat() + "Z",
        "ttl_minutes": int((row.expires_at - row.created_at).total_seconds() // 60) or int(settings.site_qr_ephemeral_ttl_minutes),
        "single_use": True,
    }


@router.post("", response_model=CompanyCreateResponse)
def create_company(
    payload: CompanyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN, UserRole.SAFETY_SPECIALIST)),
):
    if user.role != UserRole.SAFETY_SPECIALIST:
        reject_company_bound_admin_from_osgb_internal(user)
    data = payload.model_dump()
    _apply_nace_classification(data)
    if user.role == UserRole.SAFETY_SPECIALIST:
        from app.models.entities import OsgbOrganization

        org = db.get(OsgbOrganization, user.osgb_id) if user.osgb_id else None
        if org is None or not getattr(org, "is_individual", False):
            raise HTTPException(403, "İşyeri ekleme yalnız bireysel uzman çalışma alanına açıktır.")
        data["osgb_id"] = org.id
    elif user.role == UserRole.COMPANY_ADMIN:
        if not user.osgb_id:
            raise HTTPException(400, "OSGB kapsamınız tanımlı değil. EİSA yöneticisine başvurun.")
        data["osgb_id"] = user.osgb_id
    elif not data.get("osgb_id"):
        # osgb_id yazılmazsa İşyerleri’nde görünür ama ÇSGB / OSGB paneli 0 sayar
        data["osgb_id"] = _default_osgb_id(db)
    if _company_name_taken(db, payload.name, data.get("osgb_id")):
        raise HTTPException(409, "Bu OSGB kapsamında aynı adlı işyeri zaten kayıtlı.")
    obj = Company(**data)
    obj.site_verify_code = generate_site_verify_code()
    db.add(obj)
    from app.core.rls import apply_rls_user, set_rls_bypass

    try:
        # INSERT: boş allowed_company_ids + RLS WITH CHECK çakışmasın
        set_rls_bypass(db, True)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bu OSGB kapsamında aynı adlı işyeri zaten kayıtlı.")
    except Exception:
        db.rollback()
        raise
    # Yeni id henüz eski allowed_company_ids listesinde yok; RLS SELECT için yeniden hesapla.
    apply_rls_user(db, user)
    db.refresh(obj)

    login_account = None
    try:
        from app.services.osgb_admin import provision_workplace_kiosk_login

        kiosk_user, temp_password, created = provision_workplace_kiosk_login(db, obj)
        db.commit()
        login_account = {
            "user_id": kiosk_user.id,
            "email": kiosk_user.email,
            "full_name": kiosk_user.full_name,
            "temporary_password": temp_password,
            "password": temp_password,
            "created": created,
            "message": (
                "İşyeri kiosk hesabı oluşturuldu. Bu e-posta ve şifre kalıcıdır; "
                "işyerine bir kez iletin. Sonraki girişlerde aynı şifre kullanılır "
                "(yalnız OSGB şifreyi bilinçli sıfırlarsa değişir)."
            ),
        }
    except Exception:
        db.rollback()
        apply_rls_user(db, user)
        # Firma oluştu; kiosk hesabı sonra tekrar denenebilir
        login_account = None

    apply_rls_user(db, user)
    if user.role == UserRole.SAFETY_SPECIALIST:
        try:
            from app.core.rls import set_rls_bypass
            from app.services.individual_specialist import ensure_individual_workplace_assignment

            set_rls_bypass(db, True)
            ensure_individual_workplace_assignment(db, user, obj)
            db.commit()
        except Exception:
            db.rollback()
        finally:
            apply_rls_user(db, user)

    apply_rls_user(db, user)
    return CompanyCreateResponse(
        id=obj.id,
        name=obj.name,
        nace_code=obj.nace_code,
        hazard_class=obj.hazard_class,
        sgk_registry_no=obj.sgk_registry_no,
        address=obj.address,
        phone=obj.phone,
        authorized_person=obj.authorized_person,
        is_active=obj.is_active,
        osgb_id=obj.osgb_id,
        login_account=login_account,
    )


def _assert_individual_company_scope(db: Session, user: User, obj: Company) -> None:
    from app.models.entities import OsgbOrganization

    if user.role != UserRole.SAFETY_SPECIALIST or not user.osgb_id:
        raise HTTPException(403, "Bu işlem için yetkiniz yok.")
    org = db.get(OsgbOrganization, user.osgb_id)
    if org is None or not getattr(org, "is_individual", False):
        raise HTTPException(403, "İşyeri yönetimi yalnız bireysel uzman çalışma alanına açıktır.")
    if obj.osgb_id != user.osgb_id:
        raise HTTPException(403, "Yalnız kendi çalışma alanınızdaki işyerini yönetebilirsiniz.")


def _assert_company_admin_scope(user: User, obj: Company) -> None:
    reject_company_bound_admin_from_osgb_internal(user)
    if user.role == UserRole.GLOBAL_ADMIN:
        return
    if user.role != UserRole.COMPANY_ADMIN:
        raise HTTPException(403, "Bu işlem için yetkiniz yok.")
    if obj.osgb_id is not None:
        from app.core.tenant_context import assert_osgb_access, current_tenant

        if current_tenant() is not None:
            assert_osgb_access(obj.osgb_id)
            return
    if not user.osgb_id or obj.osgb_id != user.osgb_id:
        raise HTTPException(403, "Bu işyerini yönetemezsiniz — yalnızca kendi OSGB kapsamınız.")


@router.put("/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: int,
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN, UserRole.SAFETY_SPECIALIST)),
):
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
    if user.role == UserRole.SAFETY_SPECIALIST:
        _assert_individual_company_scope(db, user, obj)
    else:
        _assert_company_admin_scope(user, obj)
    data = payload.model_dump(exclude_unset=True)
    _apply_nace_classification(data, existing_nace_code=obj.nace_code)
    # OSGB admin / bireysel uzman başka OSGB'ye taşıyamaz
    if user.role in (UserRole.COMPANY_ADMIN, UserRole.SAFETY_SPECIALIST):
        data.pop("osgb_id", None)
    next_name = data.get("name", obj.name)
    next_osgb = data.get("osgb_id", obj.osgb_id)
    if "name" in data or "osgb_id" in data:
        if _company_name_taken(db, next_name, next_osgb, exclude_id=obj.id):
            raise HTTPException(409, "Bu OSGB kapsamında aynı adlı işyeri zaten kayıtlı.")
    for k, v in data.items():
        setattr(obj, k, v)
    try:
        sync_company_service_requirements(db, obj.id, commit=False)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bu OSGB kapsamında aynı adlı işyeri zaten kayıtlı.")
    db.refresh(obj)
    return obj


@router.patch("/{company_id}/deactivate")
def deactivate_company(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN, UserRole.SAFETY_SPECIALIST)),
):
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
    if user.role == UserRole.SAFETY_SPECIALIST:
        _assert_individual_company_scope(db, user, obj)
    else:
        _assert_company_admin_scope(user, obj)
    obj.is_active = False
    db.commit()
    return {"ok": True, "id": company_id, "is_active": False, "message": "Firma pasife alındı."}


@router.patch("/{company_id}/activate")
def activate_company(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN, UserRole.SAFETY_SPECIALIST)),
):
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
    if user.role == UserRole.SAFETY_SPECIALIST:
        _assert_individual_company_scope(db, user, obj)
    else:
        _assert_company_admin_scope(user, obj)
    obj.is_active = True
    db.commit()
    return {"ok": True, "id": company_id, "is_active": True, "message": "Firma yeniden aktifleştirildi."}


@router.delete("/{company_id}")
def delete_company(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN, UserRole.SAFETY_SPECIALIST)),
):
    """Kalıcı sil: bağlı operasyonel kayıtlar da silinir. Pasife alma yapılmaz."""
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
    if user.role == UserRole.SAFETY_SPECIALIST:
        _assert_individual_company_scope(db, user, obj)
    else:
        _assert_company_admin_scope(user, obj)
    name = obj.name
    try:
        _purge_company_data(db, company_id)
        db.delete(obj)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409,
            f"“{name}” silinemedi: beklenmeyen bağlı kayıt. Detay: {exc.orig or exc}",
        ) from None
    return {"ok": True, "id": company_id, "deleted": True, "message": f"“{name}” ve bağlı kayıtlar kalıcı silindi."}
