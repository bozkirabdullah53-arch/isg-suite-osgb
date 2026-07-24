from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.company_access import companies_query_for_user, ensure_company_access
from app.api.deps import get_current_user, require_roles
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
    DocumentRecord,
    DrillPhoto,
    DrillRecord,
    EisaArchiveRecord,
    EisaErrorReport,
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
    ChemicalProduct,
    PpeAssignment,
    PpeAssignmentPhoto,
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
    WorkplaceDepartment,
)
from app.models.entities import OsgbOrganization
from app.schemas.company import CompanyCreate, CompanyResponse, CompanyUpdate
from app.services.company_overview import build_company_overview
from app.services.site_verify import (
    build_ephemeral_qr_payload,
    build_qr_payload,
    create_ephemeral_session,
    generate_site_verify_code,
)

router = APIRouter(prefix="/companies", tags=["Firmalar"])


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
    db.execute(delete(SiteQrSession).where(SiteQrSession.company_id == company_id))

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
    ensure_company_access(db, user, company_id)
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
    return build_company_overview(db, obj)


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
    if not obj.site_verify_code:
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
    """Geçici saha QR (TTL, tek kullanımlık). Kalıcı QR'ı değiştirmez."""
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
        "ttl_minutes": int((row.expires_at - row.created_at).total_seconds() // 60) or 30,
        "single_use": True,
    }


@router.post("", response_model=CompanyResponse)
def create_company(
    payload: CompanyCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    data = payload.model_dump()
    if user.role == UserRole.COMPANY_ADMIN:
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
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "Bu OSGB kapsamında aynı adlı işyeri zaten kayıtlı.")
    db.refresh(obj)
    return obj


def _assert_company_admin_scope(user: User, obj: Company) -> None:
    if user.role == UserRole.GLOBAL_ADMIN:
        return
    if user.role != UserRole.COMPANY_ADMIN:
        raise HTTPException(403, "Bu işlem için yetkiniz yok.")
    if not user.osgb_id or obj.osgb_id != user.osgb_id:
        raise HTTPException(403, "Bu işyerini yönetemezsiniz — yalnızca kendi OSGB kapsamınız.")


@router.put("/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: int,
    payload: CompanyUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
    _assert_company_admin_scope(user, obj)
    data = payload.model_dump(exclude_unset=True)
    # OSGB admin başka OSGB'ye taşıyamaz
    if user.role == UserRole.COMPANY_ADMIN:
        data.pop("osgb_id", None)
    next_name = data.get("name", obj.name)
    next_osgb = data.get("osgb_id", obj.osgb_id)
    if "name" in data or "osgb_id" in data:
        if _company_name_taken(db, next_name, next_osgb, exclude_id=obj.id):
            raise HTTPException(409, "Bu OSGB kapsamında aynı adlı işyeri zaten kayıtlı.")
    for k, v in data.items():
        setattr(obj, k, v)
    try:
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
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
    _assert_company_admin_scope(user, obj)
    obj.is_active = False
    db.commit()
    return {"ok": True, "id": company_id, "is_active": False, "message": "Firma pasife alındı."}


@router.patch("/{company_id}/activate")
def activate_company(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
    _assert_company_admin_scope(user, obj)
    obj.is_active = True
    db.commit()
    return {"ok": True, "id": company_id, "is_active": True, "message": "Firma yeniden aktifleştirildi."}


@router.delete("/{company_id}")
def delete_company(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN)),
):
    """Kalıcı sil: bağlı operasyonel kayıtlar da silinir. Pasife alma yapılmaz."""
    obj = db.get(Company, company_id)
    if not obj:
        raise HTTPException(404, "Firma bulunamadı.")
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
