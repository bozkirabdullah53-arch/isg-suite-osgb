"""İBYS resmi yükleme paketi stub (gerçek İBYS API yok).

OSGB kapsamındaki işyerleri + personel CSV'lerini ZIP olarak üretir.
"""
from __future__ import annotations

import csv
import io
import zipfile
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Company, Employee

EXPORT_VERSION = "csv-package-v1"


def _companies_for_osgb(db: Session, osgb_id: int | None) -> list[Company]:
    stmt = select(Company).where(Company.is_active.is_(True)).order_by(Company.name)
    if osgb_id is not None:
        stmt = stmt.where(Company.osgb_id == osgb_id)
    return list(db.scalars(stmt).all())


def _csv_bytes(headers: list[str], rows: list[list[Any]]) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(row)
    return ("\ufeff" + buf.getvalue()).encode("utf-8")


def build_ibys_export_summary(db: Session, *, osgb_id: int | None = None) -> dict[str, Any]:
    companies = _companies_for_osgb(db, osgb_id)
    company_ids = [c.id for c in companies]
    employees: list[Employee] = []
    if company_ids:
        employees = list(
            db.scalars(
                select(Employee)
                .where(Employee.company_id.in_(company_ids))
                .order_by(Employee.company_id, Employee.full_name)
            ).all()
        )
    active_employees = sum(1 for e in employees if e.is_active)
    return {
        "export_version": EXPORT_VERSION,
        "stub": True,
        "note": "Gerçek İBYS API bağlantısı yok; resmi yükleme için CSV paketi üretilir.",
        "osgb_id": osgb_id,
        "summary": {
            "companies": len(companies),
            "employees": len(employees),
            "active_employees": active_employees,
        },
        "files": ["00-README.txt", "01-isyerleri.csv", "02-personel.csv"],
    }


def build_ibys_export_zip(db: Session, *, osgb_id: int | None = None) -> tuple[bytes, str]:
    companies = _companies_for_osgb(db, osgb_id)
    company_ids = [c.id for c in companies]
    company_names = {c.id: c.name for c in companies}
    employees: list[Employee] = []
    if company_ids:
        employees = list(
            db.scalars(
                select(Employee)
                .where(Employee.company_id.in_(company_ids))
                .order_by(Employee.company_id, Employee.full_name)
            ).all()
        )

    companies_csv = _csv_bytes(
        [
            "company_id",
            "name",
            "sgk_registry_no",
            "hazard_class",
            "address",
            "phone",
            "authorized_person",
            "tax_number",
            "nace_code",
            "is_active",
        ],
        [
            [
                c.id,
                c.name,
                c.sgk_registry_no or "",
                c.hazard_class or "",
                c.address or "",
                c.phone or "",
                c.authorized_person or "",
                c.tax_number or "",
                c.nace_code or "",
                "1" if c.is_active else "0",
            ]
            for c in companies
        ],
    )
    employees_csv = _csv_bytes(
        [
            "employee_id",
            "company_id",
            "company_name",
            "branch_id",
            "full_name",
            "national_id_masked",
            "job_title",
            "department",
            "start_date",
            "special_status",
            "is_active",
        ],
        [
            [
                e.id,
                e.company_id,
                company_names.get(e.company_id, ""),
                e.branch_id or "",
                e.full_name,
                e.national_id_masked or "",
                e.job_title or "",
                e.department or "",
                e.start_date.isoformat() if e.start_date else "",
                e.special_status or "",
                "1" if e.is_active else "0",
            ]
            for e in employees
        ],
    )
    readme = (
        "İSG Suite OSGB — İBYS yükleme paketi (stub)\n"
        f"Sürüm: {EXPORT_VERSION}\n"
        f"Üretim: {datetime.utcnow().isoformat()}Z\n"
        f"OSGB id: {osgb_id or 'all'}\n"
        f"İşyeri: {len(companies)} · Personel: {len(employees)}\n\n"
        "Dosyalar:\n"
        "- 01-isyerleri.csv : işyeri / şube kimlik alanları\n"
        "- 02-personel.csv  : personel listesi (maskeli TCKN)\n\n"
        "Not: Gerçek İBYS API entegrasyonu yoktur; resmi portala manuel yükleme için hazırlanır.\n"
    ).encode("utf-8")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("00-README.txt", readme)
        zf.writestr("01-isyerleri.csv", companies_csv)
        zf.writestr("02-personel.csv", employees_csv)
    stamp = datetime.utcnow().strftime("%Y%m%d")
    oid = osgb_id or "all"
    return buf.getvalue(), f"ibys-yukleme-paketi-{oid}-{stamp}.zip"
