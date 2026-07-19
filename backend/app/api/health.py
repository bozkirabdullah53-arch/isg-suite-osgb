"""Sağlık gözetimi API — İSG PRO 2026 Sağlık Gözetimi / Analiz parity."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.database import get_db
from app.models.entities import Company, Employee, HealthFitnessStatus, HealthRecord, HealthRecordType, User, UserRole
from app.schemas.health import HealthRecordCreate, HealthRecordResponse, HealthRecordUpdate
from app.services.health_meta import (
    MESLEK_TETKIK,
    default_next_exam,
    evaluate_blood_lead,
    suggest_for_job,
)

router = APIRouter(prefix="/health-records", tags=["Sağlık Kayıtları"])

# PRO: owner | admin | physician — Suite: admin + hekim + DSP
HEALTH_ROLES = (
    UserRole.GLOBAL_ADMIN,
    UserRole.COMPANY_ADMIN,
    UserRole.WORKPLACE_PHYSICIAN,
    UserRole.OTHER_HEALTH_PERSONNEL,
)

PHYSICIAN_ROLES = (
    UserRole.GLOBAL_ADMIN,
    UserRole.WORKPLACE_PHYSICIAN,
)

RECORD_TYPE_LABELS = {
    HealthRecordType.ENTRY_EXAM: "İşe Giriş Muayenesi",
    HealthRecordType.PERIODIC_EXAM: "Periyodik Muayene",
    HealthRecordType.RETURN_EXAM: "İşe Dönüş Muayenesi",
    HealthRecordType.JOB_CHANGE: "İş Değişikliği Muayenesi",
    HealthRecordType.NIGHT_WORK: "Gece Çalışması Muayenesi",
    HealthRecordType.HEAVY_HAZARDOUS: "Ağır ve Tehlikeli İşler",
    HealthRecordType.LAB_TEST: "Tetkik",
    HealthRecordType.VACCINATION: "Aşı",
    HealthRecordType.FITNESS_REPORT: "Uygunluk Raporu",
    HealthRecordType.OTHER: "Diğer",
}

FITNESS_LABELS = {
    HealthFitnessStatus.FIT: "Uygun",
    HealthFitnessStatus.CONDITIONAL: "Kısıtlı / Şartlı",
    HealthFitnessStatus.TRACKING: "Takip",
    HealthFitnessStatus.UNFIT: "Uygun Değil",
    HealthFitnessStatus.PENDING: "Bekliyor",
}


def ensure_access(user: User, company_id: int) -> None:
    if user.role != UserRole.GLOBAL_ADMIN and user.company_id != company_id:
        raise HTTPException(status_code=403, detail="Bu firmanın sağlık kayıtlarına erişemezsiniz.")


def _active():
    return select(HealthRecord).where(HealthRecord.deleted_at.is_(None))


def _to_response(row: HealthRecord, employee: Employee | None, include_confidential: bool) -> HealthRecordResponse:
    today = date.today()
    overdue = bool(row.next_examination_date and row.next_examination_date < today)
    data = HealthRecordResponse.model_validate(row)
    data.employee_name = employee.full_name if employee else None
    data.job_title = employee.job_title if employee else None
    data.department = employee.department if employee else None
    data.is_overdue = overdue
    if not include_confidential:
        data.confidential_note = None
    return data


def _apply_lead_eval(record: HealthRecord) -> None:
    if record.blood_lead_value is not None:
        record.blood_lead_eval = evaluate_blood_lead(record.blood_lead_value, record.blood_lead_ref)
        if not record.blood_lead_unit:
            record.blood_lead_unit = "µg/dL"
    elif record.blood_lead_value is None and record.blood_lead_eval:
        record.blood_lead_eval = None


@router.get("/meta")
def health_meta():
    return {
        "record_types": [{"code": k.value, "label": v} for k, v in RECORD_TYPE_LABELS.items()],
        "fitness_statuses": [{"code": k.value, "label": v} for k, v in FITNESS_LABELS.items()],
        "meslek_katalog": [
            {"code": k, "label": v["label"], "tests": v["tests"], "exposures": v["exposures"]}
            for k, v in MESLEK_TETKIK.items()
        ],
        "lead_eval_labels": {
            "normal": "Normal",
            "izlem": "İzlem",
            "yuksek": "Yüksek",
            "kritik": "Kritik",
        },
    }


@router.get("/suggest")
def health_suggest(
    job_title: str | None = None,
    department: str | None = None,
    user: User = Depends(require_roles(*HEALTH_ROLES)),
):
    return suggest_for_job(job_title, department)


@router.get("/summary")
def health_summary(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*HEALTH_ROLES)),
):
    effective = company_id if user.role == UserRole.GLOBAL_ADMIN else user.company_id
    if not effective:
        raise HTTPException(400, "Firma seçiniz.")
    ensure_access(user, effective)
    today = date.today()
    soon = today + timedelta(days=30)
    items = list(
        db.scalars(_active().where(HealthRecord.company_id == effective)).all()
    )
    lead_high = sum(
        1
        for i in items
        if i.blood_lead_eval in ("yuksek", "kritik") or (i.blood_lead_value is not None and (i.blood_lead_ref or 30) < i.blood_lead_value)
    )
    return {
        "company_id": effective,
        "total": len(items),
        "overdue": sum(1 for i in items if i.next_examination_date and i.next_examination_date < today),
        "due_soon": sum(
            1
            for i in items
            if i.next_examination_date and today <= i.next_examination_date <= soon
        ),
        "fit": sum(1 for i in items if i.fitness_status == HealthFitnessStatus.FIT),
        "conditional": sum(1 for i in items if i.fitness_status == HealthFitnessStatus.CONDITIONAL),
        "tracking": sum(1 for i in items if i.fitness_status == HealthFitnessStatus.TRACKING),
        "unfit": sum(1 for i in items if i.fitness_status == HealthFitnessStatus.UNFIT),
        "with_audiometry": sum(1 for i in items if i.audiometry_date or i.audiometry_result),
        "with_spirometry": sum(1 for i in items if i.spirometry_date or i.spirometry_result),
        "with_chest_xray": sum(1 for i in items if i.chest_xray_date or i.chest_xray_result),
        "with_blood_lead": sum(1 for i in items if i.blood_lead_value is not None),
        "lead_high": lead_high,
    }


@router.get("", response_model=list[HealthRecordResponse])
def list_health_records(
    company_id: int | None = None,
    employee_id: int | None = None,
    record_type: HealthRecordType | None = None,
    fitness_status: HealthFitnessStatus | None = None,
    overdue_only: bool = False,
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*HEALTH_ROLES)),
):
    effective = company_id if user.role == UserRole.GLOBAL_ADMIN else user.company_id
    query = _active().order_by(HealthRecord.examination_date.desc(), HealthRecord.id.desc())
    if effective:
        ensure_access(user, effective)
        query = query.where(HealthRecord.company_id == effective)
    if employee_id:
        query = query.where(HealthRecord.employee_id == employee_id)
    if record_type:
        query = query.where(HealthRecord.record_type == record_type)
    if fitness_status:
        query = query.where(HealthRecord.fitness_status == fitness_status)
    rows = list(db.scalars(query).all())
    emp_ids = {r.employee_id for r in rows}
    employees = {
        e.id: e
        for e in db.scalars(select(Employee).where(Employee.id.in_(emp_ids))).all()
    } if emp_ids else {}
    today = date.today()
    include_conf = user.role in PHYSICIAN_ROLES
    out = []
    for r in rows:
        emp = employees.get(r.employee_id)
        if q:
            needle = q.casefold()
            hay = f"{emp.full_name if emp else ''} {r.physician_name or ''} {r.summary or ''}".casefold()
            if needle not in hay:
                continue
        if overdue_only and not (r.next_examination_date and r.next_examination_date < today):
            continue
        out.append(_to_response(r, emp, include_conf))
    return out


@router.post("", response_model=HealthRecordResponse)
def create_health_record(
    payload: HealthRecordCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*HEALTH_ROLES)),
):
    ensure_access(user, payload.company_id)
    employee = db.get(Employee, payload.employee_id)
    if not employee or employee.company_id != payload.company_id:
        raise HTTPException(status_code=400, detail="Personel ve firma eşleşmiyor.")
    company = db.get(Company, payload.company_id)
    data = payload.model_dump()
    if not data.get("next_examination_date"):
        data["next_examination_date"] = default_next_exam(
            payload.examination_date, company.hazard_class if company else None
        )
    if not data.get("suggested_tests") and not data.get("exposures"):
        sug = suggest_for_job(employee.job_title, employee.department)
        data["suggested_tests"] = data.get("suggested_tests") or ", ".join(sug["suggested_tests"])
        data["exposures"] = data.get("exposures") or ", ".join(sug["exposures"])
    record = HealthRecord(**data, created_by_id=user.id)
    _apply_lead_eval(record)
    db.add(record)
    db.commit()
    db.refresh(record)
    return _to_response(record, employee, user.role in PHYSICIAN_ROLES)


@router.get("/export.txt")
def export_health_txt(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*HEALTH_ROLES)),
):
    effective = company_id if user.role == UserRole.GLOBAL_ADMIN else user.company_id
    if not effective:
        raise HTTPException(400, "Firma seçiniz.")
    ensure_access(user, effective)
    company = db.get(Company, effective)
    rows = list(
        db.scalars(
            _active()
            .where(HealthRecord.company_id == effective)
            .order_by(HealthRecord.examination_date.desc())
        ).all()
    )
    emp_ids = {r.employee_id for r in rows}
    employees = {
        e.id: e
        for e in db.scalars(select(Employee).where(Employee.id.in_(emp_ids))).all()
    } if emp_ids else {}
    lines = [
        "İSG Suite OSGB — Sağlık Gözetimi",
        f"Firma: {company.name if company else effective}",
        f"Olusturma: {datetime.utcnow().strftime('%d.%m.%Y %H:%M')}",
        "-" * 72,
    ]
    for r in rows:
        emp = employees.get(r.employee_id)
        name = emp.full_name if emp else f"#{r.employee_id}"
        lines.append(
            f"{r.examination_date} | {RECORD_TYPE_LABELS.get(r.record_type, r.record_type.value)} | "
            f"{name} | Hekim: {r.physician_name or '—'} | "
            f"Durum: {FITNESS_LABELS.get(r.fitness_status, r.fitness_status.value)} | "
            f"Sonraki: {r.next_examination_date or '—'}"
        )
        tetkik = []
        if r.audiometry_result or r.audiometry_date:
            tetkik.append(f"Odyo:{r.audiometry_result or r.audiometry_date}")
        if r.spirometry_result or r.spirometry_date:
            tetkik.append(f"SFT:{r.spirometry_result or r.spirometry_date}")
        if r.chest_xray_result or r.chest_xray_date:
            tetkik.append(f"Akciger:{r.chest_xray_result or r.chest_xray_date}")
        if r.blood_lead_value is not None:
            tetkik.append(f"Pb:{r.blood_lead_value}{r.blood_lead_unit or ''} ({r.blood_lead_eval or '—'})")
        if tetkik:
            lines.append(f"   Tetkik: {' | '.join(tetkik)}")
        if r.summary:
            lines.append(f"   Ozet: {r.summary}")
    body = "\n".join(lines) + "\n"
    return PlainTextResponse(
        body,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="saglik-gozetimi.txt"'},
    )


@router.patch("/{record_id}", response_model=HealthRecordResponse)
def update_health_record(
    record_id: int,
    payload: HealthRecordUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*HEALTH_ROLES)),
):
    record = db.get(HealthRecord, record_id)
    if not record or record.deleted_at:
        raise HTTPException(404, "Sağlık kaydı bulunamadı.")
    ensure_access(user, record.company_id)
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(record, k, v)
    _apply_lead_eval(record)
    db.commit()
    db.refresh(record)
    employee = db.get(Employee, record.employee_id)
    return _to_response(record, employee, user.role in PHYSICIAN_ROLES)


@router.delete("/{record_id}")
def delete_health_record(
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*HEALTH_ROLES)),
):
    record = db.get(HealthRecord, record_id)
    if not record or record.deleted_at:
        raise HTTPException(404, "Sağlık kaydı bulunamadı.")
    ensure_access(user, record.company_id)
    record.deleted_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "id": record_id}
