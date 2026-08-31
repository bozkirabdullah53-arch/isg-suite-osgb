"""EİSA — platform üst yönetimi: OSGB başvuru, abonelik, finans, paket, bildirim."""
from datetime import datetime, timedelta
import logging
from pathlib import Path
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.core.security import get_password_hash
from app.models.entities import (
    AssignmentStatus,
    AuditLog,
    EisaErrorReport,
    EisaNotificationChannel,
    EisaNotificationDeliveryStatus,
    EisaNotificationTarget,
    EisaPackage,
    EisaPaymentStatus,
    EisaPlatformNotification,
    EisaSubscriptionPayment,
    Company,
    IsgProfessional,
    OsgbApplication,
    OsgbApplicationStatus,
    OsgbOrganization,
    OsgbSubscription,
    PaymentChannel,
    SubscriptionStatus,
    User,
    UserRole,
    WorkplaceAssignment,
)
from app.schemas.eisa_platform import (
    EisaAuditLogResponse,
    EisaErrorReportCreate,
    EisaErrorReportResponse,
    EisaErrorReportUpdate,
    EisaNotificationCreate,
    EisaNotificationResponse,
    EisaOsgbAdminProvision,
    EisaOsgbAdminProvisionResponse,
    EisaOsgbUserResponse,
    EisaPackageCreate,
    EisaPackageResponse,
    EisaPackageUpdate,
    EisaPaymentCreate,
    EisaPaymentResponse,
    EisaSettingsUpdate,
    OsgbApplicationApproveResponse,
)
from app.schemas.osgb_subscription import (
    OsgbApplicationReject,
    OsgbApplicationResponse,
    OsgbSubscriptionResponse,
    OsgbSubscriptionUpdate,
)
from app.services.audit import add_audit_log
from app.services.eisa_platform import (
    ALLOWED_ERROR_STATUSES,
    audit_entry_dict,
    build_dashboard,
    create_error_report,
    error_report_response,
    filter_subscriptions,
    generate_payment_reference,
    get_settings,
    osgb_user_response,
    set_settings,
    snapshot_subscription,
    subscription_response,
)
from app.services.osgb_subscription import (
    approve_application,
    get_or_create_subscription,
)
from app.services.mailer import send_email as tracked_send_email

from app.services.osgb_admin import find_osgb_admin, provision_osgb_admin

router = APIRouter(prefix="/eisa", tags=["EİSA Platform"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


class EisaAdminPasswordResetRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    new_password: str = Field(min_length=10, max_length=128)


class EisaUserStatusRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class EisaUserStatusUpdate(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    is_active: bool | None = None
    unlock: bool = False


@router.post("/users/status")
def get_user_status(
    payload: EisaUserStatusRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    email = payload.email.strip().lower()
    target = db.scalar(select(User).where(func.lower(User.email) == email).limit(1))
    if not target:
        raise HTTPException(404, "Kullanıcı bulunamadı.")

    professional = db.scalar(
        select(IsgProfessional)
        .where(func.lower(IsgProfessional.email) == email)
        .order_by(IsgProfessional.id)
        .limit(1)
    )
    effective_osgb_id = target.osgb_id or (professional.osgb_id if professional else None)
    osgb = db.get(OsgbOrganization, effective_osgb_id) if effective_osgb_id else None
    company = db.get(Company, target.company_id) if target.company_id else None

    assignment_rows = []
    if professional:
        assignment_rows = list(
            db.execute(
                select(WorkplaceAssignment, Company)
                .join(Company, Company.id == WorkplaceAssignment.company_id)
                .where(
                    WorkplaceAssignment.professional_id == professional.id,
                    WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
                )
                .order_by(Company.name)
            ).all()
        )

    return {
        "user_id": target.id,
        "email": target.email,
        "full_name": target.full_name,
        "role": target.role.value if hasattr(target.role, "value") else str(target.role),
        "is_active": bool(target.is_active),
        "is_locked": bool(target.locked_until and target.locked_until > datetime.utcnow()),
        "locked_until": target.locked_until,
        "osgb_id": effective_osgb_id,
        "osgb_name": osgb.name if osgb else None,
        "company_id": target.company_id,
        "company_name": company.name if company else None,
        "professional_id": professional.id if professional else None,
        "professional_type": (
            professional.professional_type.value
            if professional and hasattr(professional.professional_type, "value")
            else None
        ),
        "professional_active": bool(professional.is_active) if professional else False,
        "assigned_workplaces": [
            {"id": workplace.id, "name": workplace.name}
            for _, workplace in assignment_rows
        ],
        "scope_valid": bool(
            target.role == UserRole.GLOBAL_ADMIN
            or company
            or osgb
            or professional
        ),
    }


@router.post("/users/update-status")
def update_user_status(
    payload: EisaUserStatusUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    email = payload.email.strip().lower()
    target = db.scalar(select(User).where(func.lower(User.email) == email).limit(1))
    if not target:
        raise HTTPException(404, "Kullanıcı bulunamadı.")
    if target.id == admin.id:
        raise HTTPException(400, "Kendi hesabınızın durumunu bu ekrandan değiştiremezsiniz.")
    if target.role == UserRole.GLOBAL_ADMIN:
        raise HTTPException(403, "Başka bir global yönetici hesabı bu ekrandan değiştirilemez.")

    changes = []
    if payload.is_active is not None:
        target.is_active = payload.is_active
        changes.append("aktif" if payload.is_active else "pasif")
    if payload.unlock:
        target.failed_login_count = 0
        target.locked_until = None
        changes.append("kilit kaldırıldı")

    if not changes:
        raise HTTPException(400, "Değişiklik seçilmedi.")

    target.token_version = int(getattr(target, "token_version", 0) or 0) + 1

    add_audit_log(
        db,
        user=admin,
        action="admin_user_status_updated",
        module="eisa",
        entity_type="user",
        entity_id=str(target.id),
        description=f"Kullanıcı durumu güncellendi: {target.email} ({', '.join(changes)})",
        ip_address=_client_ip(request),
    )
    db.commit()

    return {
        "ok": True,
        "email": target.email,
        "is_active": bool(target.is_active),
        "is_locked": False if payload.unlock else bool(
            target.locked_until and target.locked_until > datetime.utcnow()
        ),
        "message": f"Kullanıcı güncellendi: {', '.join(changes)}.",
    }


@router.post("/users/reset-password")
def admin_reset_user_password(
    payload: EisaAdminPasswordResetRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    # Mevcut parola okunmaz; yalnızca yeni hash yazılır.
    email = payload.email.strip().lower()
    target = db.scalar(select(User).where(func.lower(User.email) == email).limit(1))
    if not target:
        raise HTTPException(404, "Kullanıcı bulunamadı.")
    if target.id == admin.id:
        raise HTTPException(
            400,
            "Kendi parolanızı bu ekrandan değiştiremezsiniz. Güvenlik ekranını kullanın.",
        )
    if target.role == UserRole.GLOBAL_ADMIN:
        raise HTTPException(
            403,
            "Başka bir global yöneticinin parolası bu ekrandan değiştirilemez.",
        )

    target.hashed_password = get_password_hash(payload.new_password)
    target.failed_login_count = 0
    target.locked_until = None
    target.token_version = int(getattr(target, "token_version", 0) or 0) + 1

    add_audit_log(
        db,
        user=admin,
        action="admin_password_reset",
        module="eisa",
        entity_type="user",
        entity_id=str(target.id),
        description=f"Global yönetici geçici parola tanımladı: {target.email}",
        ip_address=_client_ip(request),
    )
    db.commit()

    return {
        "ok": True,
        "user_id": target.id,
        "email": target.email,
        "message": "Yeni geçici parola tanımlandı. Eski parola ve açık oturumlar geçersiz kılındı.",
    }


@router.get("/dashboard")
def eisa_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    return build_dashboard(db)


@router.get("/applications", response_model=list[OsgbApplicationResponse])
def list_applications(
    status: str | None = "pending",
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    stmt = select(OsgbApplication).order_by(OsgbApplication.created_at.desc())
    if status and status.lower() not in ("all", "*"):
        try:
            st = OsgbApplicationStatus(status)
            stmt = stmt.where(OsgbApplication.status == st)
        except ValueError:
            pass
    return list(db.scalars(stmt).all())


@router.post("/applications/{application_id}/approve", response_model=OsgbApplicationApproveResponse)
def approve(
    application_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    from app.services.osgb_admin import provision_from_application

    app_row = db.get(OsgbApplication, application_id)
    if not app_row:
        raise HTTPException(404, "Başvuru bulunamadı.")
    osgb = approve_application(db, app_row, user)
    admin_account = None
    provisioned = provision_from_application(db, app_row, osgb)
    if provisioned:
        admin_user, temp_password, created = provisioned
        admin_account = EisaOsgbAdminProvisionResponse(
            user_id=admin_user.id,
            email=admin_user.email,
            full_name=admin_user.full_name,
            temporary_password=temp_password,
            created=created,
            message="OSGB yönetici hesabı oluşturuldu." if created else "Hesap zaten vardı; şifre değiştirilmedi. Kullanıcı kendi şifresi veya şifremi unuttum ile giriş yapar.",
        )
        add_audit_log(
            db,
            user=user,
            action="osgb_admin_provisioned",
            module="eisa",
            entity_type="user",
            entity_id=str(admin_user.id),
            description=f"OSGB yönetici hesabı: {admin_user.email}",
            ip_address=_client_ip(request),
        )
    add_audit_log(
        db,
        user=user,
        action="application_approved",
        module="eisa",
        entity_type="osgb_application",
        entity_id=str(application_id),
        description=f"OSGB başvurusu onaylandı: {app_row.name}",
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(app_row)
    if admin_account:
        try:
            from app.services.email import send_email

            guide_path = Path(__file__).resolve().parents[1] / "assets" / "authenticator-kurulum.svg"
            guide_attachment = None
            if guide_path.is_file():
                guide_attachment = [{
                    "content": guide_path.read_bytes(),
                    "filename": "authenticator-kurulum-rehberi.svg",
                    "maintype": "image",
                    "subtype": "svg+xml",
                }]

            pwd_line = (
                f"Geçici şifre: {admin_account.temporary_password}\n"
                if admin_account.temporary_password
                else "Bu hesap daha önce vardı; mevcut şifrenizi kullanın veya giriş ekranındaki «Şifremi unuttum» seçeneğini kullanın.\n"
            )
            send_email(
                to_email=admin_account.email,
                subject="İSG Suite OSGB — hesabınız onaylandı",
                body=(
                    f"Merhaba {admin_account.full_name},\n\n"
                    f"{app_row.name} OSGB başvurunuz onaylandı.\n\n"
                    "Giriş bilgileri\n"
                    "---------------\n"
                    "Giriş adresi: https://www.isgsuite.tr\n"
                    f"Kullanıcı adı: {admin_account.email}\n"
                    f"{pwd_line}\n"
                    "Authenticator kurulumu ve kullanımı\n"
                    "-----------------------------------\n"
                    "1. Telefonunuza Google Authenticator veya Microsoft Authenticator uygulamasını yükleyin.\n"
                    "2. İSG Suite'e giriş yaptıktan sonra Güvenlik menüsünü açın.\n"
                    "3. MFA / Authenticator kurulumu düğmesine basın.\n"
                    "4. Ekrandaki QR kodu Authenticator uygulamasıyla okutun.\n"
                    "5. Uygulamanın ürettiği 6 haneli kodu siteye girip kurulumu tamamlayın.\n"
                    "6. Sonraki girişlerde uygulamadaki güncel 6 haneli kodu kullanın.\n\n"
                    "Güvenlik: Geçici şifrenizi ilk girişten sonra değiştirin. Authenticator kodunu kimseyle paylaşmayın.\n\n"
                    "İSG Suite OSGB"
                ),
                db=db,
                event_type="osgb_account_approved",
                recipient_name=admin_account.full_name,
                user_id=admin_account.user_id,
                osgb_id=osgb.id,
                triggered_by_user_id=user.id,
                related_type="osgb_application",
                related_id=str(application_id),
                attachments=guide_attachment,
            )
        except Exception:
            logger.warning("OSGB onay e-postası gönderilemedi", exc_info=True)
        finally:
            # Onay işlemi yukarıda zaten commit edildi; e-posta denemesi için
            # oluşturulan izleme satırını ayrı olarak kalıcılaştır.
            db.commit()
    return OsgbApplicationApproveResponse(
        application=OsgbApplicationResponse.model_validate(app_row),
        admin_account=admin_account,
    )


@router.post("/applications/{application_id}/reject", response_model=OsgbApplicationResponse)
def reject(
    application_id: int,
    payload: OsgbApplicationReject,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    app_row = db.get(OsgbApplication, application_id)
    if not app_row:
        raise HTTPException(404, "Başvuru bulunamadı.")
    if app_row.status != OsgbApplicationStatus.PENDING:
        raise HTTPException(400, "Başvuru zaten işlenmiş.")
    app_row.status = OsgbApplicationStatus.REJECTED
    app_row.rejection_reason = payload.reason.strip()
    app_row.reviewed_by_user_id = user.id
    app_row.reviewed_at = datetime.utcnow()
    add_audit_log(
        db,
        user=user,
        action="application_rejected",
        module="eisa",
        entity_type="osgb_application",
        entity_id=str(application_id),
        description=f"OSGB başvurusu reddedildi: {app_row.name}",
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(app_row)
    return app_row


@router.delete("/applications/{application_id}")
def delete_application(
    application_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    """Başvuru kaydını listeden siler. Onaylanmış OSGB / kullanıcı hesabına dokunmaz."""
    app_row = db.get(OsgbApplication, application_id)
    if not app_row:
        raise HTTPException(404, "Başvuru bulunamadı.")
    name = app_row.name
    status = app_row.status.value if hasattr(app_row.status, "value") else str(app_row.status)
    add_audit_log(
        db,
        user=user,
        action="application_deleted",
        module="eisa",
        entity_type="osgb_application",
        entity_id=str(application_id),
        description=f"OSGB başvuru kaydı silindi: {name} ({status})",
        ip_address=_client_ip(request),
    )
    db.delete(app_row)
    db.commit()
    return {"ok": True, "id": application_id, "message": "Başvuru kaydı silindi."}


@router.get("/osgb-users", response_model=list[EisaOsgbUserResponse])
def list_osgb_users(
    q: str | None = None,
    active: bool | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    stmt = select(OsgbOrganization).where(OsgbOrganization.is_individual.is_(False)).order_by(OsgbOrganization.name)
    if active is True:
        stmt = stmt.where(OsgbOrganization.is_active.is_(True), OsgbOrganization.archived_at.is_(None))
    elif active is False:
        stmt = stmt.where(
            (OsgbOrganization.is_active.is_(False)) | (OsgbOrganization.archived_at.is_not(None))
        )
    rows = list(db.scalars(stmt).all())
    out = [osgb_user_response(db, r) for r in rows]
    if q:
        needle = q.strip().lower()
        out = [
            r
            for r in out
            if needle in (r.name or "").lower()
            or needle in (r.contact_email or "").lower()
            or needle in (r.authorization_number or "").lower()
            or needle in (r.tax_number or "").lower()
        ]
    return out


@router.patch("/osgb-users/{osgb_id}/deactivate")
def deactivate_osgb(
    osgb_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    org = db.get(OsgbOrganization, osgb_id)
    if not org:
        raise HTTPException(404, "OSGB bulunamadı.")
    org.is_active = False
    org.archived_at = datetime.utcnow()
    sub = get_or_create_subscription(db, osgb_id)
    old = snapshot_subscription(sub)
    sub.status = SubscriptionStatus.SUSPENDED
    sub.updated_at = datetime.utcnow()
    add_audit_log(
        db,
        user=user,
        action="osgb_deactivated",
        module="eisa",
        entity_type="osgb_organization",
        entity_id=str(osgb_id),
        description=f"OSGB pasife alındı: {org.name}",
        old_value=old,
        new_value=snapshot_subscription(sub),
        ip_address=_client_ip(request),
    )
    db.commit()
    return {"ok": True, "id": osgb_id, "is_active": False, "message": "OSGB pasife alındı."}


@router.patch("/osgb-users/{osgb_id}/activate")
def activate_osgb(
    osgb_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    org = db.get(OsgbOrganization, osgb_id)
    if not org:
        raise HTTPException(404, "OSGB bulunamadı.")
    org.is_active = True
    org.archived_at = None

    # Kurum yeniden etkinleştirildiğinde askıdaki aboneliği de güvenli biçimde aç.
    # Veri silinmez; mevcut deneme/dönem süresi uygunsa korunur.
    sub = get_or_create_subscription(db, osgb_id)
    now = datetime.utcnow()
    if sub.status in (
        SubscriptionStatus.SUSPENDED,
        SubscriptionStatus.PAST_DUE,
        SubscriptionStatus.CANCELLED,
    ):
        if sub.current_period_ends_at and sub.current_period_ends_at > now:
            sub.status = SubscriptionStatus.ACTIVE
        else:
            sub.status = SubscriptionStatus.TRIAL
            if not sub.trial_ends_at or sub.trial_ends_at <= now:
                sub.trial_ends_at = now + timedelta(days=90)
        sub.updated_at = now

    add_audit_log(
        db,
        user=user,
        action="osgb_activated",
        module="eisa",
        entity_type="osgb_organization",
        entity_id=str(osgb_id),
        description=f"OSGB yeniden aktifleştirildi: {org.name}",
        ip_address=_client_ip(request),
    )
    db.commit()
    return {"ok": True, "id": osgb_id, "is_active": True, "message": "OSGB aktifleştirildi."}


@router.delete("/osgb-users/{osgb_id}")
def delete_osgb(
    osgb_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    """OSGB hesabını listeden kalıcı siler. Önce merkezi yedek alınır; arşiv kayıtları kalır."""
    from sqlalchemy.exc import IntegrityError

    from app.services.archive_store import create_tenant_backup
    from app.services.osgb_purge import purge_osgb

    org = db.get(OsgbOrganization, osgb_id)
    if not org:
        raise HTTPException(404, "OSGB bulunamadı.")
    name = org.name
    try:
        create_tenant_backup(db, user=user, osgb_id=osgb_id)
    except Exception as exc:
        logger.exception("OSGB silme öncesi yedek başarısız: osgb_id=%s", osgb_id)
        raise HTTPException(
            500,
            f"“{name}” silinemedi: önce merkezi yedek alınamadı. "
            "Yedek sorunu giderilmeden kalıcı silme yapılmaz.",
        ) from exc
    try:
        purge_osgb(db, osgb_id)
        add_audit_log(
            db,
            user=user,
            action="osgb_deleted",
            module="eisa",
            entity_type="osgb_organization",
            entity_id=str(osgb_id),
            description=f"OSGB kalıcı silindi: {name}",
            ip_address=_client_ip(request),
        )
        db.commit()
    except ValueError as exc:
        db.rollback()
        raise HTTPException(404, str(exc)) from None
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            409,
            f"“{name}” silinemedi: bağlı kayıtlar var. Önce Pasife Al deneyin veya destek ile iletişime geçin. ({exc.orig or exc})",
        ) from None
    return {"ok": True, "id": osgb_id, "deleted": True, "message": f"“{name}” kalıcı silindi."}


@router.post("/osgb-users/{osgb_id}/provision-admin", response_model=EisaOsgbAdminProvisionResponse)
def provision_osgb_admin_account(
    osgb_id: int,
    payload: EisaOsgbAdminProvision,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    org = db.get(OsgbOrganization, osgb_id)
    if not org:
        raise HTTPException(404, "OSGB bulunamadı.")
    email = (payload.email or org.email or "").strip().lower()
    if not email:
        raise HTTPException(422, "Yönetici e-posta adresi gerekli. OSGB iletişim e-postasını girin.")
    full_name = payload.full_name or org.responsible_manager or org.name
    admin_user, temp_password, created = provision_osgb_admin(
        db, org, email=email, full_name=full_name
    )
    add_audit_log(
        db,
        user=user,
        action="osgb_admin_provisioned",
        module="eisa",
        entity_type="user",
        entity_id=str(admin_user.id),
        description=f"OSGB yönetici hesabı: {admin_user.email}",
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(admin_user)
    return EisaOsgbAdminProvisionResponse(
        user_id=admin_user.id,
        email=admin_user.email,
        full_name=admin_user.full_name,
        temporary_password=temp_password,
        created=created,
        message="OSGB yönetici hesabı oluşturuldu." if created else "Hesap zaten vardı; şifre değiştirilmedi. Kullanıcı kendi şifresi veya şifremi unuttum ile giriş yapar.",
    )


@router.get("/subscriptions", response_model=list[OsgbSubscriptionResponse])
def list_subscriptions(
    filter: str = "all",
    q: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    return filter_subscriptions(db, filter_type=filter, q=q)


@router.get("/subscriptions/{osgb_id}", response_model=OsgbSubscriptionResponse)
def get_subscription(
    osgb_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    sub = db.scalar(select(OsgbSubscription).where(OsgbSubscription.osgb_id == osgb_id))
    if not sub:
        if not db.get(OsgbOrganization, osgb_id):
            raise HTTPException(404, "OSGB bulunamadı.")
        sub = get_or_create_subscription(db, osgb_id)
    return subscription_response(db, sub)


@router.put("/subscriptions/{osgb_id}", response_model=OsgbSubscriptionResponse)
def update_subscription(
    osgb_id: int,
    payload: OsgbSubscriptionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    if not db.get(OsgbOrganization, osgb_id):
        raise HTTPException(404, "OSGB bulunamadı.")
    sub = get_or_create_subscription(db, osgb_id)
    old = snapshot_subscription(sub)
    data = payload.model_dump(exclude_unset=True)
    if "status" in data and data["status"]:
        try:
            sub.status = SubscriptionStatus(data["status"])
        except ValueError as exc:
            raise HTTPException(422, "Geçersiz abonelik durumu.") from exc
    if "last_payment_channel" in data:
        ch = data["last_payment_channel"]
        sub.last_payment_channel = PaymentChannel(ch) if ch else None
    if "package_id" in data and data["package_id"] is not None:
        pkg = db.get(EisaPackage, data["package_id"])
        if not pkg:
            raise HTTPException(404, "Paket bulunamadı.")
        sub.package_id = pkg.id
        sub.max_users = pkg.max_users
        sub.max_workplaces = pkg.max_workplaces
    for key in (
        "trial_ends_at",
        "current_period_ends_at",
        "max_users",
        "max_workplaces",
        "payment_notes",
        "is_auto_renew",
    ):
        if key in data:
            setattr(sub, key, data[key])
    sub.updated_at = datetime.utcnow()
    add_audit_log(
        db,
        user=user,
        action="subscription_updated",
        module="eisa",
        entity_type="osgb_subscription",
        entity_id=str(sub.id),
        description=f"Abonelik güncellendi (OSGB #{osgb_id})",
        old_value=old,
        new_value=snapshot_subscription(sub),
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(sub)
    return subscription_response(db, sub)


@router.get("/packages", response_model=list[EisaPackageResponse])
def list_packages(
    active_only: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    stmt = select(EisaPackage).order_by(EisaPackage.sort_order, EisaPackage.name)
    if active_only:
        stmt = stmt.where(EisaPackage.is_active.is_(True))
    return list(db.scalars(stmt).all())


@router.post("/packages", response_model=EisaPackageResponse)
def create_package(
    payload: EisaPackageCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    code = payload.code.strip().lower()
    if db.scalar(select(EisaPackage).where(EisaPackage.code == code)):
        raise HTTPException(409, "Bu paket kodu zaten kayıtlı.")
    data = payload.model_dump()
    data["code"] = code
    obj = EisaPackage(**data)
    db.add(obj)
    add_audit_log(
        db,
        user=user,
        action="package_created",
        module="eisa",
        entity_type="eisa_package",
        description=f"Paket oluşturuldu: {obj.name}",
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.put("/packages/{package_id}", response_model=EisaPackageResponse)
def update_package(
    package_id: int,
    payload: EisaPackageUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    obj = db.get(EisaPackage, package_id)
    if not obj:
        raise HTTPException(404, "Paket bulunamadı.")
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(obj, k, v)
    obj.updated_at = datetime.utcnow()
    add_audit_log(
        db,
        user=user,
        action="package_updated",
        module="eisa",
        entity_type="eisa_package",
        entity_id=str(package_id),
        description=f"Paket güncellendi: {obj.name}",
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/packages/{package_id}")
def delete_package(
    package_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    obj = db.get(EisaPackage, package_id)
    if not obj:
        raise HTTPException(404, "Paket bulunamadı.")
    in_use = db.scalar(
        select(OsgbSubscription.id).where(OsgbSubscription.package_id == package_id).limit(1)
    )
    if in_use:
        raise HTTPException(
            409,
            f"“{obj.name}” silinemedi: aboneliklerde kullanılıyor. "
            "Önce Pasife Alın veya abonelikleri başka pakete taşıyın.",
        )
    name = obj.name
    code = obj.code
    db.delete(obj)
    add_audit_log(
        db,
        user=user,
        action="package_deleted",
        module="eisa",
        entity_type="eisa_package",
        entity_id=str(package_id),
        description=f"Paket silindi: {name} ({code})",
        ip_address=_client_ip(request),
    )
    db.commit()
    return {"ok": True, "id": package_id, "deleted": True, "message": f"“{name}” silindi."}


@router.get("/payments", response_model=list[EisaPaymentResponse])
def list_payments(
    osgb_id: int | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    stmt = select(EisaSubscriptionPayment).order_by(EisaSubscriptionPayment.payment_date.desc())
    if osgb_id:
        stmt = stmt.where(EisaSubscriptionPayment.osgb_id == osgb_id)
    if status:
        try:
            stmt = stmt.where(EisaSubscriptionPayment.payment_status == EisaPaymentStatus(status))
        except ValueError:
            pass
    rows = list(db.scalars(stmt).all())
    out = []
    for row in rows:
        org = db.get(OsgbOrganization, row.osgb_id)
        recorder = db.get(User, row.recorded_by_user_id) if row.recorded_by_user_id else None
        out.append(
            EisaPaymentResponse(
                id=row.id,
                reference_no=row.reference_no,
                osgb_id=row.osgb_id,
                osgb_name=org.name if org else None,
                subscription_id=row.subscription_id,
                amount=row.amount,
                currency=row.currency,
                payment_method=row.payment_method.value if row.payment_method else None,
                payment_status=row.payment_status.value,
                payment_date=row.payment_date,
                description=row.description,
                period_start=row.period_start,
                period_end=row.period_end,
                recorded_by_user_id=row.recorded_by_user_id,
                recorded_by_name=recorder.full_name if recorder else None,
                created_at=row.created_at,
            )
        )
    return out


@router.post("/payments", response_model=EisaPaymentResponse)
def create_payment(
    payload: EisaPaymentCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    org = db.get(OsgbOrganization, payload.osgb_id)
    if not org:
        raise HTTPException(404, "OSGB bulunamadı.")
    sub = get_or_create_subscription(db, payload.osgb_id)
    ref = (payload.reference_no or generate_payment_reference()).strip()
    if db.scalar(select(EisaSubscriptionPayment).where(EisaSubscriptionPayment.reference_no == ref)):
        raise HTTPException(409, "Bu referans numarası zaten kayıtlı.")
    try:
        pay_status = EisaPaymentStatus(payload.payment_status)
    except ValueError as exc:
        raise HTTPException(422, "Geçersiz ödeme durumu.") from exc
    method = None
    if payload.payment_method:
        try:
            method = PaymentChannel(payload.payment_method)
        except ValueError as exc:
            raise HTTPException(422, "Geçersiz ödeme yöntemi.") from exc
    row = EisaSubscriptionPayment(
        reference_no=ref,
        osgb_id=payload.osgb_id,
        subscription_id=sub.id,
        amount=payload.amount,
        currency=payload.currency,
        payment_method=method,
        payment_status=pay_status,
        payment_date=payload.payment_date or datetime.utcnow(),
        description=payload.description,
        period_start=payload.period_start,
        period_end=payload.period_end,
        recorded_by_user_id=user.id,
    )
    db.add(row)
    if pay_status == EisaPaymentStatus.COMPLETED:
        sub.last_payment_channel = method
        if payload.period_end:
            sub.current_period_ends_at = payload.period_end
            if sub.status in (SubscriptionStatus.TRIAL, SubscriptionStatus.PAST_DUE):
                sub.status = SubscriptionStatus.ACTIVE
        sub.updated_at = datetime.utcnow()
    add_audit_log(
        db,
        user=user,
        action="payment_recorded",
        module="eisa",
        entity_type="eisa_payment",
        entity_id=ref,
        description=f"Manuel ödeme kaydı: {payload.amount} {payload.currency}",
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(row)
    return EisaPaymentResponse(
        id=row.id,
        reference_no=row.reference_no,
        osgb_id=row.osgb_id,
        osgb_name=org.name,
        subscription_id=row.subscription_id,
        amount=row.amount,
        currency=row.currency,
        payment_method=row.payment_method.value if row.payment_method else None,
        payment_status=row.payment_status.value,
        payment_date=row.payment_date,
        description=row.description,
        period_start=row.period_start,
        period_end=row.period_end,
        recorded_by_user_id=row.recorded_by_user_id,
        recorded_by_name=user.full_name,
        created_at=row.created_at,
    )


@router.get("/notifications", response_model=list[EisaNotificationResponse])
def list_notifications(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    rows = list(
        db.scalars(
            select(EisaPlatformNotification).order_by(EisaPlatformNotification.created_at.desc())
        ).all()
    )
    out = []
    for row in rows:
        org = db.get(OsgbOrganization, row.target_osgb_id) if row.target_osgb_id else None
        creator = db.get(User, row.created_by_user_id) if row.created_by_user_id else None
        out.append(
            EisaNotificationResponse(
                id=row.id,
                channel=row.channel.value,
                target_scope=row.target_scope.value,
                target_osgb_id=row.target_osgb_id,
                target_osgb_name=org.name if org else None,
                title=row.title,
                message=row.message,
                status=row.status.value,
                sent_at=row.sent_at,
                created_by_user_id=row.created_by_user_id,
                created_by_name=creator.full_name if creator else None,
                created_at=row.created_at,
            )
        )
    return out


def _platform_email_recipients(
    db: Session,
    *,
    target: EisaNotificationTarget,
    target_osgb_id: int | None,
) -> list[dict]:
    """Resolve only active OSGB administrators/contact addresses, deduplicated."""
    recipients: list[dict] = []
    seen: set[str] = set()

    user_stmt = select(User).where(
        User.is_active.is_(True),
        User.role == UserRole.COMPANY_ADMIN,
        User.company_id.is_(None),
        User.osgb_id.is_not(None),
    )
    if target == EisaNotificationTarget.SELECTED_OSGB:
        user_stmt = user_stmt.where(User.osgb_id == target_osgb_id)
    for account in db.scalars(user_stmt.order_by(User.id)).all():
        email = (account.email or "").strip().casefold()
        if not email or email in seen:
            continue
        seen.add(email)
        recipients.append(
            {
                "email": account.email.strip(),
                "name": account.full_name,
                "user_id": account.id,
                "osgb_id": account.osgb_id,
            }
        )

    org_stmt = select(OsgbOrganization).where(
        OsgbOrganization.is_active.is_(True),
        OsgbOrganization.is_individual.is_(False),
    )
    if target == EisaNotificationTarget.SELECTED_OSGB:
        org_stmt = org_stmt.where(OsgbOrganization.id == target_osgb_id)
    for org in db.scalars(org_stmt.order_by(OsgbOrganization.id)).all():
        email = (org.email or "").strip().casefold()
        if not email or email in seen:
            continue
        seen.add(email)
        recipients.append(
            {
                "email": org.email.strip(),
                "name": org.responsible_manager or org.name,
                "user_id": None,
                "osgb_id": org.id,
            }
        )
    return recipients


def _send_platform_email_notification(
    db: Session,
    *,
    row: EisaPlatformNotification,
    user: User,
) -> list[dict]:
    recipients = _platform_email_recipients(
        db,
        target=row.target_scope,
        target_osgb_id=row.target_osgb_id,
    )
    results = []
    if not recipients:
        results.append(
            tracked_send_email(
                to="",
                subject=row.title,
                body=row.message,
                db=db,
                event_type="eisa_notification",
                osgb_id=row.target_osgb_id,
                triggered_by_user_id=user.id,
                related_type="eisa_platform_notification",
                related_id=str(row.id),
            )
        )
    else:
        for recipient in recipients:
            results.append(
                tracked_send_email(
                    to=recipient["email"],
                    subject=row.title,
                    body=row.message,
                    db=db,
                    event_type="eisa_notification",
                    recipient_name=recipient["name"],
                    user_id=recipient["user_id"],
                    osgb_id=recipient["osgb_id"],
                    triggered_by_user_id=user.id,
                    related_type="eisa_platform_notification",
                    related_id=str(row.id),
                )
            )
    successful = sum(1 for result in results if result.get("ok"))
    row.status = (
        EisaNotificationDeliveryStatus.SENT
        if successful
        else EisaNotificationDeliveryStatus.FAILED
    )
    row.sent_at = datetime.utcnow() if successful else None
    return results


@router.post("/notifications", response_model=EisaNotificationResponse)
def create_notification(
    payload: EisaNotificationCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    try:
        channel = EisaNotificationChannel(payload.channel)
        target = EisaNotificationTarget(payload.target_scope)
    except ValueError as exc:
        raise HTTPException(422, "Geçersiz kanal veya hedef kitle.") from exc
    if target == EisaNotificationTarget.SELECTED_OSGB and not payload.target_osgb_id:
        raise HTTPException(422, "Seçili OSGB hedefi için osgb_id gerekli.")
    if payload.target_osgb_id and not db.get(OsgbOrganization, payload.target_osgb_id):
        raise HTTPException(404, "Hedef OSGB bulunamadı.")
    row = EisaPlatformNotification(
        channel=channel,
        target_scope=target,
        target_osgb_id=payload.target_osgb_id,
        title=payload.title.strip(),
        message=payload.message.strip(),
        status=(
            EisaNotificationDeliveryStatus.QUEUED
            if channel == EisaNotificationChannel.EMAIL
            else EisaNotificationDeliveryStatus.SENT
        ),
        sent_at=None if channel == EisaNotificationChannel.EMAIL else datetime.utcnow(),
        created_by_user_id=user.id,
    )
    db.add(row)
    db.flush()
    if channel == EisaNotificationChannel.EMAIL:
        _send_platform_email_notification(db, row=row, user=user)
    add_audit_log(
        db,
        user=user,
        action="notification_sent",
        module="eisa",
        entity_type="eisa_notification",
        description=(
            f"E-posta bildirimi işlendi: {row.title}"
            if channel == EisaNotificationChannel.EMAIL
            else f"Bildirim gönderildi: {row.title}"
        ),
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(row)
    org = db.get(OsgbOrganization, row.target_osgb_id) if row.target_osgb_id else None
    return EisaNotificationResponse(
        id=row.id,
        channel=row.channel.value,
        target_scope=row.target_scope.value,
        target_osgb_id=row.target_osgb_id,
        target_osgb_name=org.name if org else None,
        title=row.title,
        message=row.message,
        status=row.status.value,
        sent_at=row.sent_at,
        created_by_user_id=row.created_by_user_id,
        created_by_name=user.full_name,
        created_at=row.created_at,
    )


@router.post("/notifications/{notification_id}/resend", response_model=EisaNotificationResponse)
def resend_notification(
    notification_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    row = db.get(EisaPlatformNotification, notification_id)
    if not row:
        raise HTTPException(404, "Bildirim bulunamadı.")
    if row.channel == EisaNotificationChannel.EMAIL:
        _send_platform_email_notification(db, row=row, user=user)
    else:
        row.status = EisaNotificationDeliveryStatus.SENT
        row.sent_at = datetime.utcnow()
    add_audit_log(
        db,
        user=user,
        action="notification_resent",
        module="eisa",
        entity_type="eisa_notification",
        entity_id=str(notification_id),
        description=(
            f"E-posta bildirimi yeniden işlendi: {row.title}"
            if row.channel == EisaNotificationChannel.EMAIL
            else f"Bildirim yeniden gönderildi: {row.title}"
        ),
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(row)
    org = db.get(OsgbOrganization, row.target_osgb_id) if row.target_osgb_id else None
    creator = db.get(User, row.created_by_user_id) if row.created_by_user_id else None
    return EisaNotificationResponse(
        id=row.id,
        channel=row.channel.value,
        target_scope=row.target_scope.value,
        target_osgb_id=row.target_osgb_id,
        target_osgb_name=org.name if org else None,
        title=row.title,
        message=row.message,
        status=row.status.value,
        sent_at=row.sent_at,
        created_by_user_id=row.created_by_user_id,
        created_by_name=creator.full_name if creator else None,
        created_at=row.created_at,
    )


@router.get("/audit-logs", response_model=list[EisaAuditLogResponse])
def list_eisa_audit_logs(
    module: str | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(min(limit, 500))
    if module:
        stmt = stmt.where(AuditLog.module == module)
    rows = list(db.scalars(stmt).all())
    out = []
    for row in rows:
        actor = db.get(User, row.user_id) if row.user_id else None
        data = audit_entry_dict(row, actor)
        out.append(EisaAuditLogResponse(**data))
    return out


@router.get("/reports/summary")
def reports_summary(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    dash = build_dashboard(db)
    return {
        "generated_at": datetime.utcnow(),
        "dashboard": dash,
        "subscriptions": filter_subscriptions(db, filter_type="all"),
        "expiring": filter_subscriptions(db, filter_type="expiring"),
        "expired": filter_subscriptions(db, filter_type="expired"),
    }


@router.get("/settings")
def get_eisa_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    return get_settings(db)


@router.put("/settings")
def update_eisa_settings(
    payload: EisaSettingsUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    updates = {}
    data = payload.model_dump(exclude_unset=True)
    for key in ("trial_days", "expiring_window_days", "support_email", "support_phone"):
        if key in data and data[key] is not None:
            updates[key] = str(data[key])
    if not updates:
        return get_settings(db)
    old = get_settings(db)
    result = set_settings(db, updates)
    add_audit_log(
        db,
        user=user,
        action="settings_updated",
        module="eisa",
        entity_type="eisa_settings",
        description="Platform ayarları güncellendi",
        old_value=str(old),
        new_value=str(result),
        ip_address=_client_ip(request),
    )
    db.commit()
    return result


@router.post("/error-reports", response_model=EisaErrorReportResponse)
def submit_error_report(
    payload: EisaErrorReportCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        row = create_error_report(
            db,
            user=user,
            source=payload.source,
            title=payload.title,
            message=payload.message,
            stack_trace=payload.stack_trace,
            user_note=payload.user_note,
            page_path=payload.page_path,
            http_method=payload.http_method,
            http_path=payload.http_path,
            http_status=payload.http_status,
            company_id=payload.company_id,
            user_agent=request.headers.get("user-agent"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    db.commit()
    db.refresh(row)
    return EisaErrorReportResponse(**error_report_response(db, row))


@router.get("/error-reports", response_model=list[EisaErrorReportResponse])
def list_error_reports(
    status: str | None = None,
    source: str | None = None,
    q: str | None = None,
    osgb_id: int | None = None,
    limit: int = 200,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    stmt = select(EisaErrorReport).order_by(EisaErrorReport.created_at.desc()).limit(min(limit, 500))
    if status:
        stmt = stmt.where(EisaErrorReport.status == status.strip().lower())
    if source:
        stmt = stmt.where(EisaErrorReport.source == source.strip().lower())
    if osgb_id:
        stmt = stmt.where(EisaErrorReport.osgb_id == osgb_id)
    rows = list(db.scalars(stmt).all())
    out = [EisaErrorReportResponse(**error_report_response(db, row)) for row in rows]
    if q:
        needle = q.strip().lower()
        out = [
            item
            for item in out
            if needle
            in " ".join(
                filter(
                    None,
                    [
                        item.title,
                        item.message,
                        item.user_email,
                        item.user_note,
                        item.http_path,
                        item.osgb_name,
                    ],
                )
            ).lower()
        ]
    return out


@router.get("/error-reports/{report_id}", response_model=EisaErrorReportResponse)
def get_error_report(
    report_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    row = db.get(EisaErrorReport, report_id)
    if not row:
        raise HTTPException(status_code=404, detail="Hata raporu bulunamadı.")
    return EisaErrorReportResponse(**error_report_response(db, row))


@router.patch("/error-reports/{report_id}", response_model=EisaErrorReportResponse)
def update_error_report(
    report_id: int,
    payload: EisaErrorReportUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(UserRole.GLOBAL_ADMIN)),
):
    row = db.get(EisaErrorReport, report_id)
    if not row:
        raise HTTPException(status_code=404, detail="Hata raporu bulunamadı.")
    data = payload.model_dump(exclude_unset=True)
    old_status = row.status
    if "status" in data and data["status"] is not None:
        status = str(data["status"]).strip().lower()
        if status not in ALLOWED_ERROR_STATUSES:
            raise HTTPException(status_code=422, detail="Geçersiz durum.")
        row.status = status
        if status in ("resolved", "ignored"):
            row.resolved_by_id = user.id
            row.resolved_at = datetime.utcnow()
        elif status in ("open", "investigating"):
            row.resolved_by_id = None
            row.resolved_at = None
    if "admin_note" in data:
        row.admin_note = data["admin_note"]
    if "admin_reply" in data:
        row.admin_reply = data["admin_reply"]
    row.updated_at = datetime.utcnow()
    add_audit_log(
        db,
        user=user,
        action="error_report_updated",
        module="eisa",
        entity_type="eisa_error_report",
        entity_id=str(row.id),
        description=f"Hata raporu güncellendi ({old_status} → {row.status})",
        old_value=old_status,
        new_value=row.status,
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(row)
    return EisaErrorReportResponse(**error_report_response(db, row))
