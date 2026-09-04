"""İşyeri kullanıcısı — personel eğitim kayıtları ve sertifika PDF indirme.

Bu modül SADECE işyeri yöneticisi (company_admin + company_id) tarafından
kullanılır. İşyeri kullanıcısı yalnızca KENDİ firmasına ait personelin eğitim
bilgilerini görebilir ve katılım belgesi PDF'ini indirebilir.

Mevcut trainings.py router'ına dokunulmaz; bu router bağımsız çalışır.
"""
from __future__ import annotations

import logging
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.company_access import effective_company_id, ensure_company_access
from app.api.deps import get_current_user, is_workplace_manager_account
from app.core.database import get_db
from app.models.entities import (
    Company,
    Employee,
    TrainingParticipant,
    TrainingSession,
    User,
    UserRole,
)
from app.services.training_pdfs import build_certificates_pdf

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/workplace/training-records",
    tags=["İşyeri Personel Eğitim Kayıtları"],
)


def _require_workplace_manager(user: User = Depends(get_current_user)) -> User:
    """Sadece işyeri yöneticisi (company_admin + company_id) kabul eder."""
    if not is_workplace_manager_account(user):
        raise HTTPException(
            status_code=403,
            detail="Bu modüle yalnızca işyeri yetkilileri erişebilir.",
        )
    return user


@router.get("")
def list_personnel_training_records(
    search: str = Query("", description="Personel adı soyadı arama filtresi"),
    db: Session = Depends(get_db),
    user: User = Depends(_require_workplace_manager),
):
    """İşyeri yöneticisinin kendi firmasına ait personelin eğitim kayıtlarını listele.

    Dönüş: Her personel için ad-soyad, unvan, departman ve katıldığı eğitimlerin
    listesi (eğitim başlığı, tarih, süre, sertifika no, geçme durumu).
    """
    company_id = user.company_id
    ensure_company_access(db, user, company_id)

    # Firma personelleri
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

    # Bu personellerin eğitim katılım kayıtları (eğitim bilgileriyle birlikte)
    tp_stmt = (
        select(TrainingParticipant)
        .options(selectinload(TrainingParticipant.training))
        .where(TrainingParticipant.employee_id.in_(emp_ids))
        .order_by(TrainingParticipant.id.desc())
    )
    participants = db.scalars(tp_stmt).all()

    # Employee id → participant list mapping
    from collections import defaultdict
    emp_trainings: dict[int, list[dict]] = defaultdict(list)
    for p in participants:
        t = p.training
        if t is None:
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


@router.get("/{employee_id}/certificates.pdf")
def download_employee_certificates_pdf(
    employee_id: int,
    training_id: int = Query(None, description="Belirli bir eğitim ID'si (boş bırakılırsa tüm eğitimler)"),
    db: Session = Depends(get_db),
    user: User = Depends(_require_workplace_manager),
):
    """İşyeri yöneticisi, kendi firmasına ait bir personelin eğitim katılım
    belgesini PDF olarak indirir.

    - training_id verilirse: Sadece o eğitimin sertifikası üretilir.
    - training_id verilmezse: Personelin tüm eğitimleri tek PDF'te üretilir.
    """
    company_id = user.company_id
    ensure_company_access(db, user, company_id)

    # Personel doğrulama — bu firmaya ait mi?
    employee = db.get(Employee, employee_id)
    if not employee or employee.company_id != company_id or not employee.is_active:
        raise HTTPException(404, "Personel bulunamadı veya bu firmaya ait değil.")

    if training_id:
        # Tek eğitim sertifikası
        row = db.scalar(
            select(TrainingSession)
            .options(selectinload(TrainingSession.participants))
            .where(TrainingSession.id == training_id)
        )
        if not row or row.company_id != company_id:
            raise HTTPException(404, "Eğitim kaydı bulunamadı.")

        # Bu personel bu eğitime katılmış mı?
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

    else:
        # Tüm eğitimler — her eğitim için ayrı sertifika üretip birleştir
        tp_stmt = (
            select(TrainingParticipant)
            .options(selectinload(TrainingParticipant.training))
            .where(TrainingParticipant.employee_id == employee_id)
            .order_by(TrainingParticipant.id.desc())
        )
        participants = db.scalars(tp_stmt).all()
        if not participants:
            raise HTTPException(422, "Bu personelin henüz eğitim kaydı yok.")

        company = db.get(Company, company_id)
        employees_map = {employee_id: employee}

        # Her eğitim için ayrı PDF üret, sonra birleştir
        all_pdf_bytes = b""
        for p in participants:
            t = p.training
            if t is None:
                continue
            # Katılımcıyı bu eğitim için filtrele
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
