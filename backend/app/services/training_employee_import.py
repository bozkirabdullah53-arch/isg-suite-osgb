"""Eğitim Excel satırlarından personel eşleme / oluşturma."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.entities import Employee


def _tc_key(tc: str | None) -> str:
    if not tc:
        return ""
    return "".join(ch for ch in str(tc) if ch.isdigit())


def resolve_or_create_employees(
    db: Session,
    company_id: int,
    rows: list[dict],
    *,
    create_missing: bool,
) -> tuple[list[dict], int]:
    """Excel satırlarını personelle eşler. Dönüş: (participants payload, created_count)."""

    def _reload_maps() -> tuple[dict[str, Employee], dict[str, Employee]]:
        existing = list(
            db.scalars(
                select(Employee).where(Employee.company_id == company_id, Employee.is_active.is_(True))
            ).all()
        )
        by_name = {e.full_name.strip().casefold(): e for e in existing if e.full_name}
        by_tc = {_tc_key(e.national_id_masked): e for e in existing if _tc_key(e.national_id_masked)}
        return by_name, by_tc

    by_name, by_tc = _reload_maps()
    created = 0
    result: list[dict] = []
    for row in rows:
        name = (row.get("full_name") or "").strip()
        if not name:
            continue
        key = name.casefold()
        tc = (row.get("national_id_masked") or "").strip() or None
        tc_digits = _tc_key(tc)
        emp = by_name.get(key) or (by_tc.get(tc_digits) if tc_digits else None)

        if not emp and create_missing:
            emp = Employee(
                company_id=company_id,
                full_name=name,
                national_id_masked=tc,
                job_title=(row.get("job_title") or None) or None,
                department=(row.get("department") or None) or None,
                is_active=True,
            )
            try:
                with db.begin_nested():
                    db.add(emp)
                    db.flush()
                by_name[key] = emp
                if tc_digits:
                    by_tc[tc_digits] = emp
                created += 1
            except IntegrityError:
                by_name, by_tc = _reload_maps()
                emp = by_name.get(key) or (by_tc.get(tc_digits) if tc_digits else None)

        result.append(
            {
                **row,
                "full_name": name,
                "employee_id": emp.id if emp else None,
                "matched": emp is not None,
            }
        )
    return result, created
