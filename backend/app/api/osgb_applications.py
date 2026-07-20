"""Herkese açık OSGB başvuru formu."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.entities import OsgbApplication, OsgbApplicationStatus
from app.schemas.osgb_subscription import OsgbApplicationCreate, OsgbApplicationResponse
from app.services.osgb_subscription import find_osgb_by_credentials

router = APIRouter(prefix="/osgb-applications", tags=["OSGB Başvuru"])


@router.post("", response_model=OsgbApplicationResponse, status_code=201)
def submit_application(payload: OsgbApplicationCreate, db: Session = Depends(get_db)):
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
        status=OsgbApplicationStatus.PENDING,
        matched_osgb_id=matched.id if matched else None,
        auto_matched=bool(matched),
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj
