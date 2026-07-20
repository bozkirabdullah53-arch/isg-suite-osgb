"""OSGB kalıcı silme — bağlı kayıtları temizler; arşiv kayıtlarının osgb_id'sini korur/nullar."""
from __future__ import annotations

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.api.companies import _purge_company_data
from app.models.entities import (
    Company,
    CrmLead,
    EisaArchiveRecord,
    EisaPlatformNotification,
    EisaSubscriptionPayment,
    FinanceTransaction,
    IsgProfessional,
    OsgbApplication,
    OsgbOrganization,
    OsgbSubscription,
    ServiceContract,
    ServiceVisit,
    User,
    UserRole,
    WorkplaceAssignment,
)


def purge_osgb(db: Session, osgb_id: int) -> str:
    """OSGB ve bağlı operasyonel veriyi kalıcı siler. Dönüş: OSGB adı."""
    org = db.get(OsgbOrganization, osgb_id)
    if not org:
        raise ValueError("OSGB bulunamadı.")
    name = org.name

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
    # Merkezi arşiv kalır; FK kopmasın diye osgb bağlantısını temizle
    db.execute(
        update(EisaArchiveRecord)
        .where(EisaArchiveRecord.osgb_id == osgb_id)
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
