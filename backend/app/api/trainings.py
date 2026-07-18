import hashlib
from datetime import date
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_roles
from app.api.files import safe_upload_root
from app.core.database import get_db
from app.models.entities import Company, Employee, TrainingParticipant, TrainingSession, TrainingStatus, User, UserRole
from app.schemas.training import TrainingCreate, TrainingResponse, TrainingUpdate, TrainingVerifyResponse
from app.services.training_excel import parse_employees_xlsx
from app.services.training_pdfs import build_attendance_pdf, build_certificates_pdf
from app.services.training_topics import meta_payload, sektor_kodu_cozumle, sectors_list_for_api


router = APIRouter(prefix="/trainings", tags=["Eğitim Yönetimi"])
EDIT_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.COMPANY_ADMIN, UserRole.SAFETY_SPECIALIST)
# test_training_rules.py bu sabiti kullanır
RULES = {"Az Tehlikeli": (8, 3), "Tehlikeli": (12, 2), "Çok Tehlikeli": (16, 1)}
LOGO_EXT = {".png", ".jpg", ".jpeg", ".webp"}
LOGO_MIME = {"image/png", "image/jpeg", "image/jpg", "image/webp"}


def ensure_access(user: User, company_id: int):
    if user.role != UserRole.GLOBAL_ADMIN and user.company_id != company_id:
        raise HTTPException(403, "Bu firmanın eğitim kayıtlarına erişemezsiniz.")


def add_years(d: date, years: int) -> date:
    try:
        return d.replace(year=d.year + years)
    except ValueError:
        return d.replace(month=2, day=28, year=d.year + years)


def _load_training(db: Session, training_id: int) -> TrainingSession:
    row = db.scalar(
        select(TrainingSession)
        .options(selectinload(TrainingSession.participants))
        .where(TrainingSession.id == training_id)
    )
    if not row:
        raise HTTPException(404, "Eğitim kaydı bulunamadı.")
    return row


def _employees_map(db: Session, training: TrainingSession) -> dict:
    ids = [p.employee_id for p in training.participants]
    if not ids:
        return {}
    return {e.id: e for e in db.scalars(select(Employee).where(Employee.id.in_(ids))).all()}


def _err_detail(data) -> str:
    detail = data if not isinstance(data, dict) else data.get("detail", data)
    if isinstance(detail, list):
        parts = []
        for item in detail:
            if isinstance(item, dict):
                parts.append(str(item.get("msg") or item))
            else:
                parts.append(str(item))
        return "; ".join(parts) or "İşlem tamamlanamadı."
    return str(detail or "İşlem tamamlanamadı.")


@router.get("/sectors")
def list_sectors():
    """Canlı uyumlu sektör listesi (auth zorunlu değil)."""
    return sectors_list_for_api()


@router.get("/meta")
def training_meta(user: User = Depends(get_current_user)):
    return meta_payload()


@router.get("/verify/{code}", response_model=TrainingVerifyResponse)
def verify_training(code: str, db: Session = Depends(get_db)):
    """Kamuya açık belge doğrulama — bakanlık / işveren kontrolü için."""
    clean = (code or "").strip().upper()
    if not clean or len(clean) < 8:
        return TrainingVerifyResponse(
            valid=False, verification_code=clean or "", message="Geçersiz doğrulama kodu."
        )
    row = db.scalar(
        select(TrainingSession)
        .options(selectinload(TrainingSession.participants))
        .where(TrainingSession.verification_code == clean)
    )
    if not row:
        return TrainingVerifyResponse(
            valid=False, verification_code=clean, message="Bu kodla eşleşen eğitim belgesi bulunamadı."
        )
    company = db.get(Company, row.company_id)
    emp_map = _employees_map(db, row)
    participants = []
    for p in row.participants:
        e = emp_map.get(p.employee_id)
        participants.append(
            {
                "full_name": e.full_name if e else f"#{p.employee_id}",
                "certificate_number": p.certificate_number,
            }
        )
    return TrainingVerifyResponse(
        valid=True,
        verification_code=clean,
        title=row.title,
        company_name=company.name if company else None,
        start_date=row.start_date,
        hazard_class=row.hazard_class,
        duration_hours=row.duration_hours,
        instructor_name=row.instructor_name,
        workplace_physician=row.workplace_physician,
        employer_representative=row.employer_representative,
        participant_count=len(participants),
        participants=participants,
        message="Belge doğrulandı.",
    )


@router.post("/parse-excel")
async def parse_excel(
    company_id: int = Query(...),
    create_missing: bool = Query(False),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    """Excel çalışan listesini okur; isteğe bağlı eksik personeli oluşturur."""
    ensure_access(user, company_id)
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Firma bulunamadı.")
    name = (file.filename or "").lower()
    if not name.endswith((".xlsx", ".xlsm")):
        raise HTTPException(422, "Yalnızca .xlsx / .xlsm dosyaları kabul edilir.")
    content = await file.read()
    try:
        rows = parse_employees_xlsx(content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not rows:
        raise HTTPException(422, "Excel dosyasında katılımcı bulunamadı.")

    existing = list(
        db.scalars(
            select(Employee).where(Employee.company_id == company_id, Employee.is_active.is_(True))
        ).all()
    )
    by_name = {e.full_name.strip().casefold(): e for e in existing if e.full_name}

    created = 0
    result = []
    for row in rows:
        key = row["full_name"].strip().casefold()
        emp = by_name.get(key)
        if not emp and create_missing:
            emp = Employee(
                company_id=company_id,
                full_name=row["full_name"].strip(),
                national_id_masked=row.get("national_id_masked") or None,
                job_title=row.get("job_title") or None,
                department=row.get("department") or None,
                is_active=True,
            )
            db.add(emp)
            db.flush()
            by_name[key] = emp
            created += 1
        result.append(
            {
                **row,
                "employee_id": emp.id if emp else None,
                "matched": emp is not None,
            }
        )
    if create_missing:
        db.commit()
    return {
        "count": len(result),
        "created": created,
        "matched": sum(1 for r in result if r["matched"]),
        "participants": result,
        "participant_ids": [r["employee_id"] for r in result if r["employee_id"]],
    }


@router.get("", response_model=list[TrainingResponse])
def list_trainings(
    q: str | None = Query(None, max_length=100),
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = (
        select(TrainingSession)
        .options(selectinload(TrainingSession.participants))
        .order_by(TrainingSession.start_date.desc())
    )
    effective = company_id if user.role == UserRole.GLOBAL_ADMIN else user.company_id
    if effective:
        query = query.where(TrainingSession.company_id == effective)
    if q:
        p = f"%{q.strip()}%"
        query = query.where(
            or_(
                TrainingSession.title.ilike(p),
                TrainingSession.instructor_name.ilike(p),
                TrainingSession.sector.ilike(p),
            )
        )
    return list(db.scalars(query).unique().all())


@router.post("", response_model=TrainingResponse)
def create_training(
    payload: TrainingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    ensure_access(user, payload.company_id)
    company = db.get(Company, payload.company_id)
    if not company:
        raise HTTPException(404, "Firma bulunamadı.")
    if payload.hazard_class not in RULES:
        raise HTTPException(422, "Geçersiz tehlike sınıfı.")
    if payload.participant_ids:
        employees = list(
            db.scalars(
                select(Employee).where(
                    Employee.id.in_(payload.participant_ids),
                    Employee.company_id == payload.company_id,
                    Employee.is_active.is_(True),
                )
            ).all()
        )
        if len(employees) != len(set(payload.participant_ids)):
            raise HTTPException(422, "Katılımcılardan biri firmaya ait değil veya pasif.")
    hours, years = RULES[payload.hazard_class]
    kod = sektor_kodu_cozumle(payload.sector)
    raw = f"{payload.company_id}|{payload.title}|{payload.start_date.isoformat()}|{user.id}"
    code = hashlib.sha256(raw.encode()).hexdigest()[:16].upper()
    values = payload.model_dump(exclude={"participant_ids"})
    values["sector"] = kod
    if not (values.get("stamp_text") or "").strip():
        values["stamp_text"] = "İSG Suite OSGB · 6331 kapsamında düzenlenmiştir"
    row = TrainingSession(
        **values,
        duration_hours=hours,
        renewal_years=years,
        next_training_date=add_years(payload.end_date or payload.start_date, years),
        verification_code=code,
        created_by_id=user.id,
    )
    db.add(row)
    db.flush()
    for eid in sorted(set(payload.participant_ids)):
        db.add(
            TrainingParticipant(
                training_id=row.id,
                employee_id=eid,
                certificate_number=f"EGT-{row.id:06d}-{eid:06d}",
            )
        )
    db.commit()
    return db.scalar(
        select(TrainingSession)
        .options(selectinload(TrainingSession.participants))
        .where(TrainingSession.id == row.id)
    )


@router.post("/{training_id}/upload-participants")
async def upload_participants(
    training_id: int,
    file: UploadFile = File(...),
    create_missing: bool = Query(True),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    """Canlı API uyumu: eğitim kaydına Excel ile katılımcı ekler."""
    row = _load_training(db, training_id)
    ensure_access(user, row.company_id)
    name = (file.filename or "").lower()
    if not name.endswith((".xlsx", ".xlsm")):
        raise HTTPException(422, "Yalnızca .xlsx / .xlsm dosyaları kabul edilir.")
    content = await file.read()
    try:
        parsed = parse_employees_xlsx(content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    if not parsed:
        raise HTTPException(422, "Excel dosyasında katılımcı bulunamadı.")

    existing = list(
        db.scalars(
            select(Employee).where(Employee.company_id == row.company_id, Employee.is_active.is_(True))
        ).all()
    )
    by_name = {e.full_name.strip().casefold(): e for e in existing if e.full_name}
    existing_ids = {p.employee_id for p in row.participants}
    added = 0
    created = 0
    for item in parsed:
        key = item["full_name"].strip().casefold()
        emp = by_name.get(key)
        if not emp and create_missing:
            emp = Employee(
                company_id=row.company_id,
                full_name=item["full_name"].strip(),
                national_id_masked=item.get("national_id_masked") or None,
                job_title=item.get("job_title") or None,
                department=item.get("department") or None,
                is_active=True,
            )
            db.add(emp)
            db.flush()
            by_name[key] = emp
            created += 1
        if not emp or emp.id in existing_ids:
            continue
        db.add(
            TrainingParticipant(
                training_id=row.id,
                employee_id=emp.id,
                certificate_number=f"EGT-{row.id:06d}-{emp.id:06d}",
            )
        )
        existing_ids.add(emp.id)
        added += 1
    db.commit()
    refreshed = _load_training(db, training_id)
    return {
        "added": added,
        "created_employees": created,
        "participant_count": len(refreshed.participants),
        "training": TrainingResponse.model_validate(refreshed),
    }


@router.post("/{training_id}/logo", response_model=TrainingResponse)
async def upload_training_logo(
    training_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    """Firma / eğitim logosu — PDF başlığına basılır."""
    row = _load_training(db, training_id)
    ensure_access(user, row.company_id)
    original = Path(file.filename or "logo.png")
    ext = original.suffix.lower()
    if ext not in LOGO_EXT or (file.content_type and file.content_type not in LOGO_MIME):
        raise HTTPException(400, "Logo için PNG veya JPG yükleyin.")
    content = await file.read(2 * 1024 * 1024 + 1)
    if len(content) > 2 * 1024 * 1024:
        raise HTTPException(413, "Logo en fazla 2 MB olabilir.")
    company_dir = safe_upload_root() / str(row.company_id) / "training-logos"
    company_dir.mkdir(parents=True, exist_ok=True)
    stored = f"{training_id}_{uuid4().hex[:10]}{ext}"
    target = (company_dir / stored).resolve()
    if safe_upload_root() not in target.parents:
        raise HTTPException(400, "Geçersiz dosya yolu.")
    target.write_bytes(content)
    row.logo_path = f"{row.company_id}/training-logos/{stored}"
    db.commit()
    return _load_training(db, training_id)


@router.patch("/{training_id}", response_model=TrainingResponse)
def update_training(
    training_id: int,
    payload: TrainingUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load_training(db, training_id)
    ensure_access(user, row.company_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(row, k, v)
    db.commit()
    return _load_training(db, training_id)


@router.get("/{training_id}/attendance.pdf")
def attendance_pdf(
    training_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = _load_training(db, training_id)
    ensure_access(user, row.company_id)
    company = db.get(Company, row.company_id)
    employees = _employees_map(db, row)
    try:
        pdf_bytes = build_attendance_pdf(
            company_name=company.name if company else str(row.company_id),
            training=row,
            employees=employees,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="egitim-{training_id}-imza-listesi.pdf"'},
    )


@router.get("/{training_id}/certificates.pdf")
def certificates_pdf(
    training_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = _load_training(db, training_id)
    ensure_access(user, row.company_id)
    if not row.participants:
        raise HTTPException(422, "Katılım belgesi için en az bir katılımcı gerekli.")
    company = db.get(Company, row.company_id)
    employees = _employees_map(db, row)
    try:
        pdf_bytes = build_certificates_pdf(
            company_name=company.name if company else str(row.company_id),
            training=row,
            employees=employees,
        )
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(500, str(exc)) from exc
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="egitim-{training_id}-katilim-belgeleri.pdf"'},
    )
