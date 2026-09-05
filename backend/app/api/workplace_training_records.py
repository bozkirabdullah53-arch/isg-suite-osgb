"""İşyeri kullanıcısı — salt-okunur eğitim kayıtları ve çalışan sağlık kartları.

Bu router SADECE işyeri yöneticisi (company_admin + company_id) tarafından
kullanılır. İşyeri kullanıcısı yalnızca KENDİ firmasına ait verileri görebilir.
Eğitim ve sağlık uçları GET-only'dir; klinik notlar, tetkik sonuçları ve rapor
belgeleri işyeri hesabına aktarılmaz.
"""
from __future__ import annotations

import logging
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.company_access import ensure_company_access
from app.api.deps import get_current_user, is_workplace_manager_account
from app.core.database import get_db
from app.models.entities import (
    Company,
    Employee,
    HealthRecord,
    TrainingParticipant,
    TrainingSession,
    User,
)
from app.services.training_pdfs import build_certificates_pdf

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/workplace",
    tags=["İşyeri Salt Okunur Kayıtları"],
)


def _require_workplace_manager(user: User = Depends(get_current_user)) -> User:
    """Sadece işyeri yöneticisi (company_admin + company_id) kabul eder."""
    if not is_workplace_manager_account(user):
        raise HTTPException(
            status_code=403,
            detail="Bu modüle yalnızca işyeri yetkilileri erişebilir.",
        )
    return user


@router.get("/training-records")
def list_personnel_training_records(
    search: str = Query("", description="Personel adı soyadı arama filtresi"),
    db: Session = Depends(get_db),
    user: User = Depends(_require_workplace_manager),
):
    """İşyeri yöneticisinin kendi firmasına ait personelin eğitim kayıtlarını listele."""
    company_id = user.company_id
    ensure_company_access(db, user, company_id)

    emp_stmt = select(Employee).where(
        Employee.company_id == company_id,
        Employee.is_active.is_(True),
    )
    if search.strip():
        like_term = f"%{search.strip()}%"
        emp_stmt = emp_stmt.where(Employee.full_name.ilike(like_term))
    emp_stmt = emp_stmt.order_by(Employee.full_name)

    employees = db.scalars(emp_stmt).all()
    if not employees:
        return {"personnel": [], "company_id": company_id}

    emp_ids = [e.id for e in employees]
    tp_stmt = (
        select(TrainingParticipant)
        .join(TrainingSession, TrainingParticipant.training_id == TrainingSession.id)
        .options(selectinload(TrainingParticipant.training))
        .where(
            TrainingParticipant.employee_id.in_(emp_ids),
            TrainingSession.company_id == company_id,
        )
        .order_by(TrainingParticipant.id.desc())
    )
    participants = db.scalars(tp_stmt).all()

    from collections import defaultdict
    emp_trainings: dict[int, list[dict]] = defaultdict(list)
    for p in participants:
        t = p.training
        if t is None or t.company_id != company_id:
            continue
        emp_trainings[p.employee_id].append({
            "training_id": t.id,
            "title": t.title or "",
            "training_type": t.training_type or "",
            "start_date": str(t.start_date) if t.start_date else None,
            "end_date": str(t.end_date) if t.end_date else None,
            "duration_hours": t.duration_hours,
            "hazard_class": t.hazard_class or "",
            "certificate_number": p.certificate_number or "",
            "exam_score": p.exam_score,
            "exam_passed": p.exam_passed,
            "status": t.status.value if t.status else "",
        })

    personnel = []
    for e in employees:
        personnel.append({
            "employee_id": e.id,
            "full_name": e.full_name,
            "job_title": e.job_title or "",
            "department": e.department or "",
            "start_date": str(e.start_date) if e.start_date else None,
            "trainings": emp_trainings.get(e.id, []),
        })

    return {"personnel": personnel, "company_id": company_id}


@router.get("/training-records/{employee_id}/certificates.pdf")
def download_employee_certificates_pdf(
    employee_id: int,
    training_id: int = Query(None, description="Belirli bir eğitim ID'si (boş bırakılırsa tüm eğitimler)"),
    db: Session = Depends(get_db),
    user: User = Depends(_require_workplace_manager),
):
    """Kendi firmasındaki personelin eğitim katılım belgesini salt-okunur indirir."""
    company_id = user.company_id
    ensure_company_access(db, user, company_id)

    employee = db.get(Employee, employee_id)
    if not employee or employee.company_id != company_id or not employee.is_active:
        raise HTTPException(404, "Personel bulunamadı veya bu firmaya ait değil.")

    if training_id:
        row = db.scalar(
            select(TrainingSession)
            .options(selectinload(TrainingSession.participants))
            .where(
                TrainingSession.id == training_id,
                TrainingSession.company_id == company_id,
            )
        )
        if not row:
            raise HTTPException(404, "Eğitim kaydı bulunamadı.")

        has_participant = any(p.employee_id == employee_id for p in row.participants)
        if not has_participant:
            raise HTTPException(422, "Bu personel belirtilen eğitime katılmamış.")

        company = db.get(Company, company_id)
        employees_map = {employee_id: employee}

        try:
            pdf_bytes = build_certificates_pdf(
                company_name=company.name if company else str(company_id),
                training=row,
                employees=employees_map,
            )
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(500, str(exc)) from exc

        safe_name = (employee.full_name or "personel").replace(" ", "_")
        filename = f"{safe_name}-egitim-{training_id}-katilim-belgesi.pdf"
        return StreamingResponse(
            BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    tp_stmt = (
        select(TrainingParticipant)
        .join(TrainingSession, TrainingParticipant.training_id == TrainingSession.id)
        .options(selectinload(TrainingParticipant.training))
        .where(
            TrainingParticipant.employee_id == employee_id,
            TrainingSession.company_id == company_id,
        )
        .order_by(TrainingParticipant.id.desc())
    )
    participants = db.scalars(tp_stmt).all()
    if not participants:
        raise HTTPException(422, "Bu personelin henüz eğitim kaydı yok.")

    company = db.get(Company, company_id)
    employees_map = {employee_id: employee}
    all_pdf_bytes = b""
    for p in participants:
        t = p.training
        if t is None or t.company_id != company_id:
            continue
        try:
            single_pdf = build_certificates_pdf(
                company_name=company.name if company else str(company_id),
                training=t,
                employees=employees_map,
            )
            all_pdf_bytes += single_pdf
        except (ValueError, RuntimeError):
            logger.warning(
                "PDF üretilemedi training_id=%s employee_id=%s",
                t.id, employee_id, exc_info=True,
            )
            continue

    if not all_pdf_bytes:
        raise HTTPException(422, "Hiçbir eğitim için sertifika üretilemedi.")

    safe_name = (employee.full_name or "personel").replace(" ", "_")
    filename = f"{safe_name}-tum-egitim-belgeleri.pdf"
    return StreamingResponse(
        BytesIO(all_pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/health-cards")
def list_employee_health_cards(
    search: str = Query("", description="Personel adı soyadı arama filtresi"),
    db: Session = Depends(get_db),
    user: User = Depends(_require_workplace_manager),
):
    """Kendi işyerindeki çalışanların sınırlı sağlık kartı özetini döndürür.

    Klinik not, tanı, tetkik sonucu, rapor dosyası veya diğer hassas sağlık
    alanları bu endpointte özellikle yer almaz. Her çalışan için yalnız son
    muayene kaydının tarih/tür/uygunluk özeti gösterilir.
    """
    company_id = user.company_id
    ensure_company_access(db, user, company_id)

    emp_stmt = select(Employee).where(
        Employee.company_id == company_id,
        Employee.is_active.is_(True),
    )
    if search.strip():
        emp_stmt = emp_stmt.where(Employee.full_name.ilike(f"%{search.strip()}%"))
    employees = list(db.scalars(emp_stmt.order_by(Employee.full_name)).all())
    if not employees:
        return {"personnel": [], "company_id": company_id}

    emp_ids = [e.id for e in employees]
    records = list(
        db.scalars(
            select(HealthRecord)
            .where(
                HealthRecord.company_id == company_id,
                HealthRecord.employee_id.in_(emp_ids),
                HealthRecord.deleted_at.is_(None),
            )
            .order_by(
                HealthRecord.employee_id,
                HealthRecord.examination_date.desc(),
                HealthRecord.id.desc(),
            )
        ).all()
    )
    latest_by_employee: dict[int, HealthRecord] = {}
    for record in records:
        latest_by_employee.setdefault(record.employee_id, record)

    personnel = []
    for employee in employees:
        record = latest_by_employee.get(employee.id)
        personnel.append({
            "employee_id": employee.id,
            "full_name": employee.full_name,
            "job_title": employee.job_title or "",
            "department": employee.department or "",
            "last_examination_date": str(record.examination_date) if record and record.examination_date else None,
            "next_examination_date": str(record.next_examination_date) if record and record.next_examination_date else None,
            "record_type": record.record_type.value if record and record.record_type else None,
            "fitness_status": record.fitness_status.value if record and record.fitness_status else None,
        })

    return {"personnel": personnel, "company_id": company_id}
