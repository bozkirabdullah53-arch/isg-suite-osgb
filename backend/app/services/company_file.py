"""Firma 360 / Tam Firma Dosyası için salt okunur veri derleyicisi.

Bu servis mevcut durum merkezini yeniden kullanır ve rapor çıktısı için gereken
ayrıntıları ekler. Yeni bir kayıt kaynağı oluşturmaz; sağlık verilerini kişi
ve tanı bilgisi olmadan toplu tutar, ticari alanları da yalnızca OSGB/global
yöneticisine verir.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import (
    Branch,
    Company,
    DocumentCategory,
    DocumentRecord,
    Employee,
    FinanceTransaction,
    OsgbOrganization,
    UserRole,
    WorkplaceAssignment,
)
from app.services.workplace_status import build_workplace_status


FINANCE_STATUS_LABELS = {
    "pending": "Bekliyor",
    "paid": "Ödendi",
    "overdue": "Vadesi geçti",
    "cancelled": "İptal",
}


def can_view_company_commercial(viewer) -> bool:
    """OSGB yöneticisi ile işyeri hesabını kesin olarak ayırır.

    Her iki hesap da ``company_admin`` rolünü kullanabildiği için yalnız role
    bakmak güvenli değildir. İşyeri hesabında company_id doludur; OSGB hesabı
    şirket bağı olmadan çalışır.
    """
    return bool(
        viewer
        and (
            viewer.role == UserRole.GLOBAL_ADMIN
            or (viewer.role == UserRole.COMPANY_ADMIN and not viewer.company_id)
        )
    )


def _iso(value):
    return value.isoformat() if value is not None else None


def _effective_finance_status(row: FinanceTransaction, today: date) -> str:
    status = str(row.status or "pending")
    if (
        row.transaction_type == "income"
        and status == "pending"
        and row.due_date is not None
        and row.due_date < today
    ):
        return "overdue"
    return status


def _build_finance_details(db: Session, company_id: int, today: date) -> dict:
    rows = list(
        db.scalars(
            select(FinanceTransaction)
            .where(FinanceTransaction.company_id == company_id)
            .order_by(FinanceTransaction.transaction_date.desc(), FinanceTransaction.id.desc())
        ).all()
    )
    normalized = []
    monthly = defaultdict(lambda: {"income": 0, "expense": 0, "net_paid": 0})
    for row in rows:
        status = _effective_finance_status(row, today)
        amount = int(row.amount or 0)
        transaction_type = str(row.transaction_type or "income")
        month = row.transaction_date.strftime("%Y-%m") if row.transaction_date else "—"
        if status != "cancelled":
            monthly[month][transaction_type] = monthly[month].get(transaction_type, 0) + amount
        if status == "paid":
            monthly[month]["net_paid"] += amount if transaction_type == "income" else -amount
        normalized.append(
            {
                "id": row.id,
                "description": row.description,
                "transaction_type": transaction_type,
                "transaction_type_label": "Gelir" if transaction_type == "income" else "Gider",
                "category": row.category,
                "amount": amount,
                "status": status,
                "status_label": FINANCE_STATUS_LABELS.get(status, status),
                "transaction_date": _iso(row.transaction_date),
                "due_date": _iso(row.due_date),
            }
        )

    active = [row for row in normalized if row["status"] != "cancelled"]
    income = [row for row in active if row["transaction_type"] == "income"]
    expense = [row for row in active if row["transaction_type"] == "expense"]
    paid_income = sum(row["amount"] for row in income if row["status"] == "paid")
    paid_expense = sum(row["amount"] for row in expense if row["status"] == "paid")
    receivable_rows = [row for row in income if row["status"] in {"pending", "overdue"}]
    overdue_rows = [row for row in receivable_rows if row["status"] == "overdue"]
    due_soon_rows = [
        row
        for row in receivable_rows
        if row["status"] == "pending"
        and row["due_date"]
        and date.fromisoformat(row["due_date"]) <= today + timedelta(days=30)
        and date.fromisoformat(row["due_date"]) >= today
    ]
    pending_expense = [row for row in expense if row["status"] in {"pending", "overdue"}]

    return {
        "summary": {
            "transaction_count": len(normalized),
            "income_accrued": sum(row["amount"] for row in income),
            "income_paid": paid_income,
            "receivable": sum(row["amount"] for row in receivable_rows),
            "overdue_receivable": sum(row["amount"] for row in overdue_rows),
            "due_soon_receivable": sum(row["amount"] for row in due_soon_rows),
            "expense_total": sum(row["amount"] for row in expense),
            "expense_paid": paid_expense,
            "pending_expense": sum(row["amount"] for row in pending_expense),
            "net_paid": paid_income - paid_expense,
            "net_position": sum(row["amount"] for row in income)
            - sum(row["amount"] for row in expense),
        },
        "recent": normalized[:8],
        "transactions": normalized,
        "monthly": [
            {"month": month, **values}
            for month, values in sorted(monthly.items(), reverse=True)
        ],
        # Eski ekranın beklediği alan korunur; yeni özet daha doğru ayrımları
        # summary altında verir.
        "pending_amount": sum(row["amount"] for row in active if row["status"] in {"pending", "overdue"}),
    }


def _build_workforce_summary(db: Session, company_id: int) -> dict:
    employees = list(db.scalars(select(Employee).where(Employee.company_id == company_id)).all())
    branches = list(db.scalars(select(Branch).where(Branch.company_id == company_id)).all())
    branch_names = {branch.id: branch.name for branch in branches}
    branch_counts = defaultdict(lambda: {"total": 0, "active": 0})
    departments = Counter()
    job_titles = Counter()
    for employee in employees:
        branch_key = branch_names.get(employee.branch_id, "Merkez / şube atanmamış")
        branch_counts[branch_key]["total"] += 1
        if employee.is_active:
            branch_counts[branch_key]["active"] += 1
        if employee.department:
            departments[employee.department] += 1
        if employee.job_title:
            job_titles[employee.job_title] += 1

    return {
        "total": len(employees),
        "active": sum(1 for employee in employees if employee.is_active),
        "inactive": sum(1 for employee in employees if not employee.is_active),
        "by_branch": [
            {"name": name, **counts}
            for name, counts in sorted(branch_counts.items(), key=lambda item: item[0].lower())
        ],
        "by_department": [
            {"name": name, "count": count}
            for name, count in departments.most_common()
        ],
        "by_job_title": [
            {"name": name, "count": count}
            for name, count in job_titles.most_common()
        ],
    }


def build_company_file(db: Session, company: Company, *, viewer=None) -> dict:
    """Build the complete, read-only company dossier for UI and exports."""
    today = date.today()
    commercial = can_view_company_commercial(viewer)
    payload = build_workplace_status(db, company, viewer=viewer)

    company_data = dict(payload.get("company") or {})
    company_data.update(
        {
            "tax_number": company.tax_number,
            "risk_assessment_date": _iso(company.risk_assessment_date),
            "risk_document_no": company.risk_document_no,
            "risk_revision_no": company.risk_revision_no,
            "visit_qr_enabled": bool(company.visit_qr_enabled),
        }
    )
    payload["company"] = company_data

    branch_rows = list(
        db.scalars(
            select(Branch)
            .where(Branch.company_id == company.id)
            .order_by(Branch.is_active.desc(), Branch.name)
        ).all()
    )
    payload["branches"] = [
        {
            "id": branch.id,
            "name": branch.name,
            "sgk_registry_no": branch.sgk_registry_no,
            "city": branch.city,
            "address": branch.address,
            "is_active": bool(branch.is_active),
        }
        for branch in branch_rows
    ]
    payload["workforce"] = _build_workforce_summary(db, company.id)

    document_rows = list(
        db.scalars(
            select(DocumentRecord)
            .where(DocumentRecord.company_id == company.id)
            .order_by(DocumentRecord.valid_until.asc().nullslast(), DocumentRecord.id.desc())
        ).all()
    )
    documents = []
    for document in document_rows:
        is_health = document.category == DocumentCategory.HEALTH
        documents.append(
            {
                "id": document.id,
                "category": document.category.value if document.category else "general",
                "title": "Sağlık belgesi" if is_health else document.title,
                "file_name": None if is_health else document.file_name,
                "valid_from": _iso(document.valid_from),
                "valid_until": _iso(document.valid_until),
                "version": document.version,
                "is_active": bool(document.is_active),
            }
        )
    payload["documents"] = documents

    payload["assignment_contract_files"] = [
        {
            "assignment_id": assignment.id,
            "professional_type": assignment.professional_type.value
            if assignment.professional_type
            else None,
            "file_name": assignment.contract_file_name,
            "content_type": assignment.contract_content_type,
            "has_file": bool(assignment.contract_storage_path or assignment.contract_file_name),
        }
        for assignment in db.scalars(
            select(WorkplaceAssignment)
            .where(WorkplaceAssignment.company_id == company.id)
            .order_by(WorkplaceAssignment.id.desc())
        ).all()
        if assignment.contract_file_name or assignment.contract_storage_path
    ]

    osgb = db.get(OsgbOrganization, company.osgb_id) if company.osgb_id else None
    payload["osgb_profile"] = {
        "name": osgb.name if osgb else None,
        "authorization_number": osgb.authorization_number if osgb else None,
        "responsible_manager": osgb.responsible_manager if osgb else None,
        "email": osgb.email if osgb else None,
        "phone": osgb.phone if osgb else None,
    }

    if commercial:
        payload["finance"] = _build_finance_details(db, company.id, today)
        contracts = payload.get("contracts") or []
        payload["contract_summary"] = {
            "total": len(contracts),
            "active": sum(1 for row in contracts if str(row.get("status")) == "active"),
            "expiring_soon": sum(1 for row in contracts if row.get("expiring_soon")),
            "monthly_recurring": sum(int(row.get("monthly_fee") or 0) for row in contracts if str(row.get("status")) == "active"),
        }
    else:
        payload.pop("finance", None)
        payload.pop("contracts", None)
        payload.pop("contract_summary", None)

    payload["report"] = {
        "title": "Tam Firma Dosyası",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "as_of_date": today.isoformat(),
        "commercial_details_visible": commercial,
        "medical_data_mode": "aggregate_only",
        "sections": [
            "Firma kimliği",
            "İSG durum merkezi",
            "Şubeler ve işgücü özeti",
            "Belge envanteri",
            "Terminler ve sorumlular",
        ]
        + (["OSGB sözleşmeleri", "Cari ve finans"] if commercial else []),
    }
    return payload
