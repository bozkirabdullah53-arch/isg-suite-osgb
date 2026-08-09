"""OSGB kalıcı silme — bağlı kayıtları temizler; arşiv kayıtlarının osgb_id'sini korur/nullar."""
from __future__ import annotations

from sqlalchemy import delete, select, text, update
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
)
from app.models.personnel_profile import (
    PersonnelProfile,
    PersonnelProfileCompetency,
    PersonnelProfileContact,
    PersonnelProfileExperience,
)
from app.models.personnel_profile_document import PersonnelProfileDocument


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


def purge_osgb(db: Session, osgb_id: int) -> str:
    """OSGB ve bağlı operasyonel veriyi kalıcı siler. Dönüş: OSGB adı."""
    org = db.get(OsgbOrganization, osgb_id)
    if not org:
        raise ValueError("OSGB bulunamadı.")
    name = org.name

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

    companies = list(db.scalars(select(Company).where(Company.osgb_id == osgb_id)).all())
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

    # OSGB yöneticilerini askıya al / bağını kopar (global admin'e dokunma)
    users = list(
        db.scalars(
            select(User).where(User.osgb_id == osgb_id, User.role != UserRole.GLOBAL_ADMIN)
        ).all()
    )
    for u in users:
        u.osgb_id = None
        u.company_id = None
        u.is_active = False

    db.delete(org)
    db.flush()
    return name
