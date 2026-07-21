"""Aylik sozlesme tahakkuku — aktif ServiceContract -> pending gelir."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import FinanceTransaction, ServiceContract


def accrual_key(contract_id: int, month: date | None = None) -> str:
    m = month or date.today()
    return f"TAHAKKUK-{contract_id}-{m.strftime('%Y-%m')}"


def accrue_month_for_osgb(db: Session, osgb_id: int, as_of: date | None = None) -> dict:
    """Aktif sozlesmeler icin bu ay tahakkuk olustur (idempotent)."""
    today = as_of or date.today()
    month_tag = today.strftime("%Y-%m")
    contracts = list(
        db.scalars(
            select(ServiceContract).where(
                ServiceContract.osgb_id == osgb_id,
                ServiceContract.status == "active",
            )
        ).all()
    )

    created: list[dict] = []
    skipped = 0
    for contract in contracts:
        fee = int(contract.monthly_fee or 0)
        if fee <= 0:
            skipped += 1
            continue
        if contract.start_date and contract.start_date > today:
            skipped += 1
            continue
        if contract.end_date and contract.end_date < today:
            skipped += 1
            continue

        key = accrual_key(contract.id, today)
        existing = db.scalar(
            select(FinanceTransaction).where(
                FinanceTransaction.osgb_id == osgb_id,
                FinanceTransaction.description.is_not(None),
                FinanceTransaction.description.contains(key),
            )
        )
        if existing:
            skipped += 1
            continue

        fin = FinanceTransaction(
            osgb_id=osgb_id,
            company_id=contract.company_id,
            transaction_type="income",
            category="contract",
            amount=fee,
            transaction_date=today,
            due_date=today + timedelta(days=30),
            status="pending",
            description=f"{key} aylik tahakkuk ({month_tag})",
        )
        db.add(fin)
        db.flush()
        created.append(
            {
                "finance_id": fin.id,
                "contract_id": contract.id,
                "company_id": contract.company_id,
                "amount": fee,
                "key": key,
            }
        )

    db.commit()
    return {
        "osgb_id": osgb_id,
        "month": month_tag,
        "created_count": len(created),
        "skipped_count": skipped,
        "created": created,
    }
