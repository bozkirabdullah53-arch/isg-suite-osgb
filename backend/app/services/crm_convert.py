"""CRM fırsat → işyeri + sözleşme + ilk tahakkuk."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.entities import Company, CrmLead, FinanceTransaction, ServiceContract
from app.services.site_verify import generate_site_verify_code


def _find_or_create_company(db: Session, lead: CrmLead) -> Company:
    existing = db.scalar(
        select(Company).where(
            Company.osgb_id == lead.osgb_id,
            func.lower(Company.name) == lead.company_name.strip().casefold(),
        )
    )
    if existing:
        if lead.contact_name and not existing.authorized_person:
            existing.authorized_person = lead.contact_name
        if lead.phone and not existing.phone:
            existing.phone = lead.phone
        if lead.hazard_class and not existing.hazard_class:
            existing.hazard_class = lead.hazard_class
        if not existing.site_verify_code:
            existing.site_verify_code = generate_site_verify_code()
        return existing

    # Unique name globally — if conflict under another OSGB, suffix
    name = lead.company_name.strip()
    clash = db.scalar(select(Company).where(func.lower(Company.name) == name.casefold()))
    if clash:
        name = f"{name} (OSGB-{lead.osgb_id})"
        again = db.scalar(select(Company).where(func.lower(Company.name) == name.casefold()))
        if again and again.osgb_id == lead.osgb_id:
            return again
        if again:
            name = f"{lead.company_name.strip()} #{lead.id}"

    company = Company(
        name=name,
        sgk_registry_no=f"CRM-{lead.id}-{date.today().strftime('%y%m%d')}",
        hazard_class=lead.hazard_class or "Tehlikeli",
        phone=lead.phone,
        authorized_person=lead.contact_name,
        osgb_id=lead.osgb_id,
        site_verify_code=generate_site_verify_code(),
        is_active=True,
    )
    db.add(company)
    db.flush()
    return company


def _contract_payload(contract: ServiceContract) -> dict:
    return {
        "id": contract.id,
        "contract_number": contract.contract_number,
        "company_id": contract.company_id,
        "monthly_fee": contract.monthly_fee,
        "start_date": contract.start_date.isoformat() if contract.start_date else None,
        "end_date": contract.end_date.isoformat() if contract.end_date else None,
        "status": contract.status,
    }


def convert_lead_to_contract(db: Session, lead: CrmLead) -> dict:
    if lead.stage == "lost":
        raise HTTPException(400, "Kaybedilmiş fırsat sözleşmeye dönüştürülemez.")
    if lead.estimated_monthly_value is None or int(lead.estimated_monthly_value) < 0:
        raise HTTPException(422, "Teklif tutarı (aylık) geçersiz.")

    # Idempotency: already converted?
    existing_no = f"CRM-{lead.id}"
    prior = db.scalar(select(ServiceContract).where(ServiceContract.contract_number == existing_no))
    if prior:
        lead.stage = "won"
        db.commit()
        db.refresh(lead)
        company = db.get(Company, prior.company_id)
        return {
            "lead": lead,
            "company_id": prior.company_id,
            "company_name": company.name if company else None,
            "contract": _contract_payload(prior),
            "finance_id": None,
            "already_converted": True,
        }

    company = _find_or_create_company(db, lead)
    today = date.today()
    contract = ServiceContract(
        osgb_id=lead.osgb_id,
        company_id=company.id,
        contract_number=existing_no,
        start_date=today,
        end_date=today + timedelta(days=365),
        monthly_fee=int(lead.estimated_monthly_value or 0),
        status="active",
    )
    db.add(contract)
    db.flush()

    finance = None
    fee = int(lead.estimated_monthly_value or 0)
    if fee > 0:
        finance = FinanceTransaction(
            osgb_id=lead.osgb_id,
            company_id=company.id,
            transaction_type="income",
            category="contract",
            amount=fee,
            transaction_date=today,
            due_date=today + timedelta(days=30),
            status="pending",
            description=f"CRM-{lead.id} ilk ay tahakkuk ({company.name})",
        )
        db.add(finance)
        db.flush()

    lead.stage = "won"
    db.commit()
    db.refresh(lead)
    db.refresh(contract)
    if finance:
        db.refresh(finance)

    return {
        "lead": lead,
        "company_id": company.id,
        "company_name": company.name,
        "contract": _contract_payload(contract),
        "finance_id": finance.id if finance else None,
        "already_converted": False,
    }
