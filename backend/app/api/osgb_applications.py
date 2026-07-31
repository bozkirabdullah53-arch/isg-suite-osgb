"""Herkese açık OSGB başvuru formu."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from sqlalchemy.exc import SQLAlchemyError

from app.core.database import get_db
from app.models.entities import OsgbApplication, OsgbApplicationStatus
from app.schemas.osgb_subscription import OsgbApplicationCreate, OsgbApplicationResponse
from app.services.eisa_platform import resolved_trial_days
from app.services.osgb_subscription import find_osgb_by_credentials

router = APIRouter(prefix="/osgb-applications", tags=["OSGB Başvuru"])


@router.get("/public-info")
def public_application_info(db: Session = Depends(get_db)):
    """Başvuru formu için herkese açık deneme süresi bilgisi."""
    days = resolved_trial_days(db)
    return {
        "trial_days": days,
        "note": f"Onay sonrası {days} günlük ücretsiz deneme süresi başlar.",
    }


@router.post("", response_model=OsgbApplicationResponse, status_code=201)
def submit_application(payload: OsgbApplicationCreate, db: Session = Depends(get_db)):
    if not payload.contract_accepted or not payload.personal_data_accepted:
        raise HTTPException(400, "Sözleşme ve kişisel verilerin korunması onayı zorunludur.")

    pending = db.scalar(
        select(OsgbApplication).where(
            OsgbApplication.status == OsgbApplicationStatus.PENDING,
            OsgbApplication.authorization_number == payload.authorization_number.strip(),
        )
    )
    if pending:
        raise HTTPException(409, "Bu yetki numarası ile bekleyen bir başvuru zaten var.")

    matched = find_osgb_by_credentials(
        db,
        authorization_number=payload.authorization_number,
        tax_number=payload.tax_number,
    )
    obj = OsgbApplication(
        name=payload.name.strip(),
        authorization_number=payload.authorization_number.strip(),
        tax_number=payload.tax_number.strip(),
        responsible_manager=payload.responsible_manager,
        contact_email=str(payload.contact_email).lower(),
        contact_phone=payload.contact_phone,
        address=payload.address,
        applicant_name=payload.applicant_name.strip(),
        applicant_email=str(payload.applicant_email).lower(),
        notes=payload.notes,
        contract_accepted=payload.contract_accepted,
        personal_data_accepted=payload.personal_data_accepted,
        status=OsgbApplicationStatus.PENDING,
        matched_osgb_id=matched.id if matched else None,
        auto_matched=bool(matched),
    )
    db.add(obj)
    try:
        db.commit()
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            500,
            "Başvuru kaydedilemedi. Veritabanı şeması güncelleniyor olabilir; birkaç dakika sonra tekrar deneyin.",
        ) from exc
    db.refresh(obj)
    return obj
