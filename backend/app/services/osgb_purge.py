"""OSGB kalıcı silme — bağlı kayıtları temizler; arşiv kayıtlarının osgb_id'sini korur/nullar."""
from __future__ import annotations

import logging

from sqlalchemy import delete, inspect, or_, select, text, update
from sqlalchemy.orm import Session

from app.api.companies import _purge_company_data
from app.models.entities import (
    Company,
    CrmLead,
    EisaArchiveRecord,
    EisaErrorReport,
    EisaPlatformNotification,
    EisaSubscriptionPayment,
    FinanceTransaction,
    HealthAccessLog,
    HealthRecordRevision,
    IntegrationDryRunLog,
    IsgProfessional,
    LegalAcceptance,
    OrganizationMembership,
    OsgbApplication,
    OsgbOrganization,
    OsgbSubscription,
    ServiceContract,
    ServiceVisit,
    User,
    UserRole,
    WorkplaceAssignment,
    WorkplaceMembership,
)
from app.models.personnel_profile import (
    PersonnelProfile,
    PersonnelProfileCompetency,
    PersonnelProfileContact,
    PersonnelProfileExperience,
)
from app.models.personnel_profile_document import PersonnelProfileDocument
from app.services.user_retirement import anonymize_orphan_user, orphan_account_state

logger = logging.getLogger(__name__)


def _set_health_audit_append_only_triggers(db: Session, enabled: bool) -> None:
    """OSGB purge sırasında tenant sağlık denetim satırlarını kontrollü temizle.

    Sağlık revizyonu ve erişim kayıtları normal akışta değiştirilemez/silinemez.
    Ancak OSGB kalıcı silme işlemi merkezi yedek alındıktan sonra tenant verisini
    tamamen kaldıran açık bir yönetici işlemidir. PostgreSQL/SQLite trigger'ları
    yalnız bu kısa transaction aralığında kaldırılır ve hemen yeniden kurulur.
    """
    bind = db.get_bind()
    if bind is None:
        return
    inspector = inspect(bind)

    tables = ("health_record_revisions", "health_access_logs")
    existing = [table for table in tables if inspector.has_table(table)]
    if not existing:
        return

    if bind.dialect.name == "postgresql":
        for table in existing:
            trigger = f"trg_{table}_append_only"
            function = f"prevent_{table}_mutation"
            db.execute(text(f"DROP TRIGGER IF EXISTS {trigger} ON {table}"))
            if enabled:
                db.execute(
                    text(
                        f"""
                        CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$
                        BEGIN
                          RAISE EXCEPTION '{table} is append-only';
                        END;
                        $$ LANGUAGE plpgsql;
                        """
                    )
                )
                db.execute(
                    text(
                        f"CREATE TRIGGER {trigger} BEFORE UPDATE OR DELETE ON {table} "
                        f"FOR EACH ROW EXECUTE FUNCTION {function}()"
                    )
                )
    elif bind.dialect.name == "sqlite":
        for table in existing:
            db.execute(text(f"DROP TRIGGER IF EXISTS trg_{table}_no_update"))
            db.execute(text(f"DROP TRIGGER IF EXISTS trg_{table}_no_delete"))
            if enabled:
                db.execute(
                    text(
                        f"CREATE TRIGGER IF NOT EXISTS trg_{table}_no_update "
                        f"BEFORE UPDATE ON {table} BEGIN "
                        f"SELECT RAISE(ABORT, '{table} is append-only'); END"
                    )
                )
                db.execute(
                    text(
                        f"CREATE TRIGGER IF NOT EXISTS trg_{table}_no_delete "
                        f"BEFORE DELETE ON {table} BEGIN "
                        f"SELECT RAISE(ABORT, '{table} is append-only'); END"
                    )
                )


def _purge_osgb_health_audit_logs(db: Session, osgb_id: int) -> None:
    """Firma silinmeden önce tenant sağlık denetim kayıtlarını kaldır.

    Bu kayıtlar companies.id ve health_records.id'ye FK tuttuğu için şirket
    silme sırasının en başında temizlenmelidir. Normal sağlık kayıtlarının
    append-only kuralı korunur; yalnız kalıcı OSGB purge transaction'ında
    trigger'lar geçici olarak devre dışı bırakılır.
    """
    company_ids = list(
        db.scalars(select(Company.id).where(Company.osgb_id == osgb_id)).all()
    )
    if not company_ids:
        return

    _set_health_audit_append_only_triggers(db, enabled=False)
    try:
        db.execute(
            delete(HealthAccessLog).where(HealthAccessLog.company_id.in_(company_ids))
        )
        db.execute(
            delete(HealthRecordRevision).where(
                HealthRecordRevision.company_id.in_(company_ids)
            )
        )
        db.flush()
    finally:
        try:
            _set_health_audit_append_only_triggers(db, enabled=True)
        except Exception:
            # PostgreSQL transaction rollback restores the dropped trigger if
            # recreation fails; preserve the original purge exception for the
            # caller and let the endpoint rollback the whole transaction.
            logger.exception("Sağlık denetim trigger'ları yeniden kurulamadı")


def _purge_osgb_personnel_profiles(db: Session, osgb_id: int) -> None:
    """OSGB'ye ait dijital personel kartlarını, özne kayıtlarından önce temizler.

    Personel ekranındaki "Sil" işlemi Employee satırını fiziksel olarak silmez;
    yalnız pasife alır. Bu nedenle OSGB kalıcı silinirken pasif çalışanlara ait
    PersonnelProfile satırları da hâlâ Employee/Company/OSGB FK'larını tutabilir.
    Global FK davranışını değiştirmek yerine yalnız tenant purge akışında çocuk
    tabloları güvenli sırada kaldırıyoruz.
    """
    profile_ids = list(
        db.scalars(
            select(PersonnelProfile.id).where(PersonnelProfile.osgb_id == osgb_id)
        ).all()
    )
    if not profile_ids:
        return

    # Sürümlü alt tablolarda kendi içlerindeki supersedes_id bağları nullable'dır.
    # Önce bu zinciri çözmek, ardından aynı profile ait bütün sürümleri silmek
    # PostgreSQL RESTRICT davranışında deterministik bir silme sırası sağlar.
    db.execute(
        update(PersonnelProfileDocument)
        .where(PersonnelProfileDocument.profile_id.in_(profile_ids))
        .values(supersedes_id=None)
    )
    db.execute(
        update(PersonnelProfileContact)
        .where(PersonnelProfileContact.profile_id.in_(profile_ids))
        .values(supersedes_id=None)
    )
    db.execute(
        update(PersonnelProfileCompetency)
        .where(PersonnelProfileCompetency.profile_id.in_(profile_ids))
        .values(supersedes_id=None)
    )
    db.execute(
        update(PersonnelProfileExperience)
        .where(PersonnelProfileExperience.profile_id.in_(profile_ids))
        .values(supersedes_id=None)
    )

    db.execute(
        delete(PersonnelProfileDocument).where(
            PersonnelProfileDocument.profile_id.in_(profile_ids)
        )
    )
    db.execute(
        delete(PersonnelProfileContact).where(
            PersonnelProfileContact.profile_id.in_(profile_ids)
        )
    )
    db.execute(
        delete(PersonnelProfileCompetency).where(
            PersonnelProfileCompetency.profile_id.in_(profile_ids)
        )
    )
    db.execute(
        delete(PersonnelProfileExperience).where(
            PersonnelProfileExperience.profile_id.in_(profile_ids)
        )
    )
    db.execute(delete(PersonnelProfile).where(PersonnelProfile.id.in_(profile_ids)))
    db.flush()


def _purge_osgb_training_participants(db: Session, osgb_id: int) -> None:
    """OSGB personellerine bağlı eğitim katılımlarını tenant SELECT'inden bağımsız temizler.

    EİSA global yönetici kalıcı silme akışında ORM/tenant görünürlük filtreleri,
    `_purge_company_data` içindeki önce-ID-topla yaklaşımında Employee kimlik listesini
    boş bırakabilir. Ardından doğrudan Employee DELETE çalıştığında PostgreSQL,
    training_participants.employee_id FK'sı nedeniyle işlemi durdurur.

    Buradaki parametrik SQL yalnız kalıcı OSGB purge akışında çalışır; eğitim CRUD,
    sertifika, geçmiş veya normal personel silme davranışını değiştirmez.
    """
    db.execute(
        text(
            """
            DELETE FROM training_participants
            WHERE employee_id IN (
                SELECT e.id
                FROM employees AS e
                JOIN companies AS c ON c.id = e.company_id
                WHERE c.osgb_id = :osgb_id
            )
            """
        ),
        {"osgb_id": osgb_id},
    )
    db.flush()


def _purge_osgb_ohs_committee_residuals(db: Session, osgb_id: int) -> None:
    """Şirket silinmeden önce İSG Kurulu'nun yeni alt tablolarını çocuk→ana sırada temizler.

    `app.api.companies._purge_company_data` eski kurul ana tablolarını
    (ohs_committee_meetings / ohs_committee_members) temizliyor. Daha sonra eklenen
    signature_steps, meeting_versions ve duplicate_reports tabloları da doğrudan
    companies.id FK'sı tuttuğundan, yalnız OSGB kalıcı silme akışında bunları önce
    kaldırmak gerekir. Normal İSG Kurulu CRUD akışı ve global FK/CASCADE şeması değişmez.
    """
    company_scope = "SELECT id FROM companies WHERE osgb_id = :osgb_id"
    for table_name in (
        "ohs_committee_signature_steps",
        "ohs_committee_meeting_versions",
        "ohs_committee_duplicate_reports",
    ):
        db.execute(
            text(
                f"DELETE FROM {table_name} "
                f"WHERE company_id IN ({company_scope})"
            ),
            {"osgb_id": osgb_id},
        )
    db.flush()


def _collect_osgb_user_ids(db: Session, osgb_id: int, company_ids: list[int]) -> list[int]:
    """OSGB silinmeden önce bütün tenant kullanıcılarını kimlikleriyle yakala.

    `_purge_company_data` kullanıcıların `company_id` bağını kopardığı için bu
    sorgu şirket silinmeden önce çalışmalıdır. Eski kiosk hesapları `osgb_id`
    taşımıyor olabilir; doğrudan işyeri veya üyelik bağları bu nedenle ayrıca
    kapsanır.
    """
    scope_clauses = [
        User.osgb_id == osgb_id,
        User.id.in_(
            select(OrganizationMembership.user_id).where(
                OrganizationMembership.osgb_id == osgb_id
            )
        ),
    ]
    if company_ids:
        scope_clauses.extend(
            (
                User.company_id.in_(company_ids),
                User.id.in_(
                    select(WorkplaceMembership.user_id).where(
                        WorkplaceMembership.company_id.in_(company_ids)
                    )
                ),
            )
        )

    return list(
        db.scalars(
            select(User.id).where(
                User.role != UserRole.GLOBAL_ADMIN,
                or_(*scope_clauses),
            )
        ).all()
    )


def _retire_osgb_users(
    db: Session,
    osgb_id: int,
    company_ids: list[int],
    user_ids: list[int],
) -> None:
    """Silinen OSGB'nin hesaplarını kapat, eski JWT'leri de geçersizleştir.

    Kullanıcının başka bir OSGB/işyeri üyeliği varsa hesabı tamamen yok edilmez;
    yalnız silinen tenant bağları kaldırılır ve eski oturumları yenilenmeye
    zorlanır. Başka kapsamı kalmayan hesap pasif + anonim hale getirilir.
    """
    if not user_ids:
        return

    company_scope = set(company_ids)
    users = list(
        db.scalars(
            select(User).where(
                User.id.in_(user_ids),
                User.role != UserRole.GLOBAL_ADMIN,
            )
        ).all()
    )
    for user in users:
        was_active = bool(user.is_active)
        if user.osgb_id == osgb_id:
            user.osgb_id = None
        if user.company_id in company_scope:
            user.company_id = None

        # get_current_user ve /auth/refresh bu alanı kontrol eder. Artırmak,
        # silme anındaki mevcut access/refresh JWT'lerini de anında düşürür.
        user.is_active = False
        user.token_version = int(getattr(user, "token_version", 0) or 0) + 1
        state = orphan_account_state(db, user)
        if bool(state.get("eligible")):
            anonymize_orphan_user(db, user)
        elif was_active:
            # Başka bir tenant kapsamı olan çoklu üyelik hesabı çalışmaya devam
            # eder; ancak artırılmış token_version nedeniyle yeniden giriş yapar.
            user.is_active = True

    db.flush()


def purge_osgb(db: Session, osgb_id: int) -> str:
    """OSGB ve bağlı operasyonel veriyi kalıcı siler. Dönüş: OSGB adı."""
    org = db.get(OsgbOrganization, osgb_id)
    if not org:
        raise ValueError("OSGB bulunamadı.")
    name = org.name
    companies = list(db.scalars(select(Company).where(Company.osgb_id == osgb_id)).all())
    company_ids = [company.id for company in companies]

    # Şirket purge'ü User.company_id bağını koparmadan önce tenant hesaplarının
    # tamamını kimlikleriyle yakala. Aksi halde eski işyeri/kiosk hesapları aktif
    # kalıp silinmiş OSGB üzerinden giriş yapmaya devam edebilir.
    osgb_user_ids = _collect_osgb_user_ids(db, osgb_id, company_ids)

    # Sağlık denetim kayıtları companies/health_records FK'ları tuttuğu için
    # şirket purge'ünden önce kaldırılır. Aksi halde companies silme işlemi
    # health_access_logs gibi append-only kayıtlar nedeniyle yarıda kalır.
    _purge_osgb_health_audit_logs(db, osgb_id)

    # Dijital personel kartları Employee/Company/OSGB üzerinde RESTRICT FK tutar.
    # Şirket purge'ü Employee satırlarını fiziksel olarak silmeden önce bunlar
    # kaldırılmalıdır. Bu yalnız kalıcı OSGB silme akışında çalışır.
    _purge_osgb_personnel_profiles(db, osgb_id)

    # Global EİSA purge sırasında tenant görünürlük filtresine bağlı Employee-ID
    # toplamasına güvenmeden eğitim katılım FK'sını doğrudan çözer.
    _purge_osgb_training_participants(db, osgb_id)

    # İSG Kurulu'nun yeni sürüm/imza/mükerrer rapor tabloları şirketi doğrudan
    # referanslar; mevcut company purge eski ana tabloları silmeden önce temizle.
    _purge_osgb_ohs_committee_residuals(db, osgb_id)

    for company in companies:
        _purge_company_data(db, company.id)
        db.delete(company)
    db.flush()

    db.execute(delete(EisaSubscriptionPayment).where(EisaSubscriptionPayment.osgb_id == osgb_id))
    db.execute(delete(OsgbSubscription).where(OsgbSubscription.osgb_id == osgb_id))
    db.execute(delete(ServiceVisit).where(ServiceVisit.osgb_id == osgb_id))
    db.execute(delete(WorkplaceAssignment).where(WorkplaceAssignment.osgb_id == osgb_id))
    db.execute(delete(ServiceContract).where(ServiceContract.osgb_id == osgb_id))
    db.execute(delete(CrmLead).where(CrmLead.osgb_id == osgb_id))
    db.execute(delete(FinanceTransaction).where(FinanceTransaction.osgb_id == osgb_id))
    db.execute(delete(IsgProfessional).where(IsgProfessional.osgb_id == osgb_id))
    # İBYS/KATİP dry-run logları OSGB'ye FK tutar; silinmezse IntegrityError
    db.execute(delete(IntegrationDryRunLog).where(IntegrationDryRunLog.osgb_id == osgb_id))

    # Kullanıcı sözleşme/kabul kayıtları hukuki kayıt olarak korunur; yalnız OSGB bağı koparılır.
    db.execute(
        update(LegalAcceptance)
        .where(LegalAcceptance.osgb_id == osgb_id)
        .values(osgb_id=None)
    )
    # Çoklu OSGB üyelikleri doğrudan organizasyona bağlıdır ve organizasyonla birlikte silinir.
    db.execute(
        delete(OrganizationMembership).where(OrganizationMembership.osgb_id == osgb_id)
    )

    db.execute(
        update(OsgbApplication)
        .where(OsgbApplication.matched_osgb_id == osgb_id)
        .values(matched_osgb_id=None)
    )
    db.execute(
        update(EisaPlatformNotification)
        .where(EisaPlatformNotification.target_osgb_id == osgb_id)
        .values(target_osgb_id=None)
    )
    # Merkezi arşiv / hata raporları kalır; FK kopmasın diye osgb bağlantısını temizle
    db.execute(
        update(EisaArchiveRecord)
        .where(EisaArchiveRecord.osgb_id == osgb_id)
        .values(osgb_id=None)
    )
    db.execute(
        update(EisaErrorReport)
        .where(EisaErrorReport.osgb_id == osgb_id)
        .values(osgb_id=None)
    )

    # OSGB'ye bağlı bütün hesapları kapat. Başka aktif üyeliği/profesyonel
    # kapsamı olan çoklu tenant hesapları yalnız silinen bağdan ayrılır;
    # kapsamı kalmayanlar anonimleştirilir. Global admin'e dokunulmaz.
    _retire_osgb_users(db, osgb_id, company_ids, osgb_user_ids)

    db.delete(org)
    db.flush()
    return name
