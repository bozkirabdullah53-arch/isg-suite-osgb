"""Sağlık gözetimi API — İSG PRO 2026 Sağlık Gözetimi / Analiz parity."""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from html import escape as html_escape
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse
from openpyxl import Workbook
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.api.company_access import (
    company_ids_for_query,
    effective_company_id,
    ensure_company_access,
    find_professional_for_user,
)
from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.input_rules import assert_date_order, assert_event_date
from app.core.database import get_db
from app.models.entities import (
    AssignmentStatus,
    Company,
    Employee,
    HealthAccessLog,
    HealthFitnessStatus,
    HealthRecord,
    HealthRecordRevision,
    HealthRecordType,
    IsgProfessional,
    ProfessionalType,
    User,
    UserRole,
    WorkplaceAssignment,
)
from app.schemas.health import HealthRecordCreate, HealthRecordResponse, HealthRecordUpdate
from app.services.health_field_crypto import DecryptedRecordView, encrypt_payload
from app.services.health_audit import (
    append_health_access,
    append_health_revision,
    verify_access_chain,
    verify_revision_chain,
)
from app.services.health_meta import (
    EXPOSURE_OPTIONS,
    MESLEK_TETKIK,
    build_analysis_payload,
    default_next_exam,
    evaluate_blood_lead,
    smart_summary,
    suggest_for_job,
    tetkik_summary,
)
from app.services.upload_gateway import delete_relative, persist_relative
from app.services.upload_security import assert_safe_upload

router = APIRouter(prefix="/health-records", tags=["Sağlık Kayıtları"])

HEALTH_SUPPORT_ROLES = (
    UserRole.WORKPLACE_PHYSICIAN,
    UserRole.OTHER_HEALTH_PERSONNEL,
)
PHYSICIAN_ROLES = (
    UserRole.WORKPLACE_PHYSICIAN,
)
PHYSICIAN_ONLY = (UserRole.WORKPLACE_PHYSICIAN,)
ALLOWED_REPORT = {".pdf", ".jpg", ".jpeg", ".png", ".docx"}

DSP_CREATE_FIELDS = {
    "company_id", "employee_id", "record_type", "examination_date",
    "next_examination_date", "informed_consent", "physician_professional_id",
    "audiometry_date", "spirometry_date", "chest_xray_date",
    "blood_lead_date", "blood_lead_value", "blood_lead_unit", "blood_lead_ref",
}
DSP_UPDATE_FIELDS = DSP_CREATE_FIELDS - {"company_id", "employee_id"}


def _enforce_write_matrix(user: User, supplied_fields: set[str], *, create: bool) -> None:
    if user.role == UserRole.WORKPLACE_PHYSICIAN:
        return
    allowed = DSP_CREATE_FIELDS if create else DSP_UPDATE_FIELDS
    forbidden = sorted(supplied_fields - allowed)
    if forbidden:
        raise HTTPException(
            status_code=403,
            detail=(
                "DSP bu klinik alanları değiştiremez: " + ", ".join(forbidden)
                + ". Klinik değerlendirme, sonuç, uygunluk ve kısıt kararları yalnız işyeri hekimine aittir."
            ),
        )


def _active_assigned_physicians(db: Session, company_id: int) -> list[IsgProfessional]:
    today = date.today()
    return list(
        db.scalars(
            select(IsgProfessional)
            .join(WorkplaceAssignment, WorkplaceAssignment.professional_id == IsgProfessional.id)
            .where(
                WorkplaceAssignment.company_id == company_id,
                WorkplaceAssignment.professional_type == ProfessionalType.WORKPLACE_PHYSICIAN,
                WorkplaceAssignment.status == AssignmentStatus.ACTIVE,
                WorkplaceAssignment.start_date <= today,
                or_(WorkplaceAssignment.end_date.is_(None), WorkplaceAssignment.end_date >= today),
                IsgProfessional.professional_type == ProfessionalType.WORKPLACE_PHYSICIAN,
                IsgProfessional.is_active.is_(True),
            )
            .order_by(IsgProfessional.full_name, IsgProfessional.id)
        ).unique().all()
    )


def _resolve_assigned_physician(
    db: Session,
    *,
    user: User,
    company_id: int,
    requested_id: int | None,
) -> IsgProfessional:
    assigned = _active_assigned_physicians(db, company_id)
    if user.role == UserRole.WORKPLACE_PHYSICIAN:
        own = find_professional_for_user(db, user)
        if not own or all(p.id != own.id for p in assigned):
            raise HTTPException(403, "Bu işyerinde aktif işyeri hekimi görevlendirmeniz bulunmuyor.")
        if requested_id is not None and requested_id != own.id:
            raise HTTPException(403, "Hekim sağlık kaydını yalnız kendi aktif görevlendirmesiyle imzalayabilir.")
        return own
    if requested_id is None:
        if len(assigned) == 1:
            return assigned[0]
        raise HTTPException(422, "DSP kaydı için aktif görevlendirilmiş işyeri hekimi seçilmelidir.")
    selected = next((p for p in assigned if p.id == requested_id), None)
    if not selected:
        raise HTTPException(422, "Seçilen hekim bu işyerinde aktif görevlendirilmiş işyeri hekimi değildir.")
    return selected

RECORD_TYPE_LABELS = {
    HealthRecordType.ENTRY_EXAM: "İşe Giriş Muayenesi",
    HealthRecordType.PERIODIC_EXAM: "Periyodik Muayene",
    HealthRecordType.RETURN_EXAM: "İşe Dönüş Muayenesi",
    HealthRecordType.JOB_CHANGE: "İş Değişikliği Muayenesi",
    HealthRecordType.NIGHT_WORK: "Gece Çalışması Muayenesi",
    HealthRecordType.HEAVY_HAZARDOUS: "Ağır ve Tehlikeli İşler",
    HealthRecordType.SPECIAL_RISK: "Özel Risk / Göreve Özgü",
    HealthRecordType.OCCUPATIONAL_DISEASE_SUSPECT: "Meslek Hastalığı Şüphesi",
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


def ensure_access(db: Session, user: User, company_id: int) -> None:
    ensure_company_access(db, user, company_id)


def _upload_root() -> Path:
    return Path(settings.upload_dir).resolve()


def _active():
    return select(HealthRecord).where(HealthRecord.deleted_at.is_(None))


def _to_response(row: HealthRecord, employee: Employee | None, include_confidential: bool) -> HealthRecordResponse:
    today = date.today()
    overdue = bool(row.next_examination_date and row.next_examination_date < today)
    view = DecryptedRecordView(row)
    data = HealthRecordResponse.model_validate(row)
    for field in (
        "confidential_note",
        "summary",
        "restrictions",
        "audiometry_result",
        "spirometry_result",
        "chest_xray_result",
        "follow_up_note",
        "other_biological_test",
        "exposures",
        "suggested_tests",
    ):
        setattr(data, field, getattr(view, field))
    data.employee_name = employee.full_name if employee else None
    data.job_title = employee.job_title if employee else None
    data.department = employee.department if employee else None
    data.is_overdue = overdue
    data.has_report = bool(row.report_storage_path)
    data.smart_summary = smart_summary(view, employee)
    data.tetkik_summary = tetkik_summary(view)
    if not include_confidential:
        # P0-07: hassas klinik metin yalnız hekim/GA
        from app.services.health_field_crypto import SENSITIVE_TEXT_FIELDS

        for field in SENSITIVE_TEXT_FIELDS:
            setattr(data, field, None)
        # DSP klinik karar üretmez; liste yanıtı hekim uygunluk kararını da
        # taşımamalıdır. Kayıt ve dosya kapsamı yine atama + tenant ile korunur.
        data.fitness_status = None
        data.blood_lead_eval = None
        data.smart_summary = None
        data.tetkik_summary = None
    return data


def _apply_lead_eval(record: HealthRecord) -> None:
    if record.blood_lead_value is not None:
        record.blood_lead_eval = evaluate_blood_lead(record.blood_lead_value, record.blood_lead_ref)
        if not record.blood_lead_unit:
            record.blood_lead_unit = "µg/dL"
    elif record.blood_lead_value is None and record.blood_lead_eval:
        record.blood_lead_eval = None


def _validate_health_date_pair(
    *,
    examination_date: date | None,
    next_examination_date: date | None,
) -> tuple[date, date | None]:
    try:
        exam_date = assert_event_date(
            examination_date,
            label="Muayene tarihi",
            allow_future_days=0,
        )
        next_date = assert_event_date(
            next_examination_date,
            label="Sonraki muayene",
            required=False,
            allow_future_days=3650,
        )
        assert_date_order(
            exam_date,
            next_date,
            earlier_label="Muayene tarihi",
            later_label="Sonraki muayene",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return exam_date, next_date


def _validate_periodic_exam_ceiling(
    *,
    record_type: HealthRecordType,
    examination_date: date,
    next_examination_date: date | None,
    hazard_class: str | None,
    special_status: str | None = None,
) -> None:
    """Periyodik muayene tarihini mevzuattaki azami aralıkta tutar.

    Hekim daha kısa bir aralık belirleyebilir; yalnızca azami periyodu aşan
    yeni/güncellenen tarihleri reddeder. Mevcut kayıtlar geriye dönük
    değiştirilmez.
    """
    if record_type != HealthRecordType.PERIODIC_EXAM or not next_examination_date:
        return
    ceiling = default_next_exam(examination_date, hazard_class, special_status)
    if next_examination_date > ceiling:
        raise HTTPException(
            status_code=422,
            detail=(
                "Periyodik muayene için sonraki tarih mevzuattaki azami periyodu "
                f"aşamaz ({ceiling.isoformat()} tarihine kadar). "
                "İşyeri hekimi risk değerlendirmesine göre daha kısa tarih seçebilir."
            ),
        )


def _company_records(db: Session, company_id: int) -> list[HealthRecord]:
    return list(
        db.scalars(
            _active()
            .where(HealthRecord.company_id == company_id)
            .order_by(HealthRecord.examination_date.desc(), HealthRecord.id.desc())
        ).all()
    )


def _employees_map(db: Session, emp_ids: set[int]) -> dict[int, Employee]:
    if not emp_ids:
        return {}
    return {
        e.id: e
        for e in db.scalars(select(Employee).where(Employee.id.in_(emp_ids))).all()
    }


@router.get("/meta")
def health_meta(user: User = Depends(require_roles(*HEALTH_SUPPORT_ROLES))):
    _ = user
    return {
        "record_types": [{"code": k.value, "label": v} for k, v in RECORD_TYPE_LABELS.items()],
        "fitness_statuses": [{"code": k.value, "label": v} for k, v in FITNESS_LABELS.items()],
        "exposure_options": EXPOSURE_OPTIONS,
        "meslek_katalog": [
            {
                "code": k,
                "label": v["label"],
                "tests": v["tests"],
                "exposures": v["exposures"],
                "period": v.get("period") or "",
            }
            for k, v in MESLEK_TETKIK.items()
        ],
        "lead_eval_labels": {
            "normal": "Normal",
            "izlem": "İzlem",
            "yuksek": "Yüksek",
            "kritik": "Kritik",
        },
    }


@router.get("/assigned-physicians")
def assigned_physicians(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*HEALTH_SUPPORT_ROLES)),
):
    ensure_access(db, user, company_id)
    rows = _active_assigned_physicians(db, company_id)
    if user.role == UserRole.WORKPLACE_PHYSICIAN:
        own = find_professional_for_user(db, user)
        rows = [p for p in rows if own and p.id == own.id]
    return [
        {
            "professional_id": p.id,
            "full_name": p.full_name,
            "certificate_number": p.certificate_number,
        }
        for p in rows
    ]


@router.get("/suggest")
def health_suggest(
    job_title: str | None = None,
    department: str | None = None,
    user: User = Depends(require_roles(*PHYSICIAN_ONLY)),
):
    _ = user
    return suggest_for_job(job_title, department)


@router.get("/lead-eval")
def health_lead_eval(
    value: float | None = None,
    ref: float | None = 30,
    user: User = Depends(require_roles(*PHYSICIAN_ONLY)),
):
    _ = user
    code = evaluate_blood_lead(value, ref)
    labels = {"normal": "Normal", "izlem": "İzlem", "yuksek": "Yüksek", "kritik": "Kritik"}
    return {"code": code, "label": labels.get(code or "", "—"), "value": value, "ref": ref}


@router.get("/summary")
def health_summary(
    request: Request,
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*HEALTH_SUPPORT_ROLES)),
):
    effective = effective_company_id(db, user, company_id)
    today = date.today()
    soon = today + timedelta(days=30)
    items = _company_records(db, effective)
    lead_high = sum(
        1
        for i in items
        if i.blood_lead_eval in ("yuksek", "kritik")
        or (i.blood_lead_value is not None and (i.blood_lead_ref or 30) < i.blood_lead_value)
    )
    payload = {
        "company_id": effective,
        "total": len(items),
        "overdue": sum(1 for i in items if i.next_examination_date and i.next_examination_date < today),
        "due_soon": sum(
            1 for i in items if i.next_examination_date and today <= i.next_examination_date <= soon
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
    if user.role == UserRole.OTHER_HEALTH_PERSONNEL:
        for key in ("fit", "conditional", "tracking", "unfit", "lead_high"):
            payload[key] = None
    append_health_access(
        db, actor=user, company_id=effective, action="summary_view", request=request,
        metadata={"record_count": len(items)},
    )
    db.commit()
    return payload


@router.get("/analysis")
def health_analysis(
    request: Request,
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*PHYSICIAN_ONLY)),
):
    effective = effective_company_id(db, user, company_id)
    records = _company_records(db, effective)
    emp_map = _employees_map(db, {r.employee_id for r in records})
    all_emps = list(
        db.scalars(
            select(Employee).where(Employee.company_id == effective, Employee.is_active.is_(True))
        ).all()
    )
    company = db.get(Company, effective)
    payload = build_analysis_payload(records, emp_map, all_employees=all_emps)
    payload["company_id"] = effective
    payload["company_name"] = company.name if company else str(effective)
    append_health_access(
        db, actor=user, company_id=effective, action="analysis_view", request=request,
        metadata={"record_count": len(records)},
    )
    db.commit()
    return payload


@router.get("/analysis.txt")
def health_analysis_txt(
    request: Request,
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*PHYSICIAN_ONLY)),
):
    effective = effective_company_id(db, user, company_id)
    records = _company_records(db, effective)
    emp_map = _employees_map(db, {r.employee_id for r in records})
    all_emps = list(
        db.scalars(
            select(Employee).where(Employee.company_id == effective, Employee.is_active.is_(True))
        ).all()
    )
    company = db.get(Company, effective)
    d = build_analysis_payload(records, emp_map, all_employees=all_emps)
    lines = [
        "SAĞLIK ANALİZ MERKEZİ RAPORU",
        f"Firma: {company.name if company else effective}",
        f"Oluşturma: {datetime.utcnow().strftime('%d.%m.%Y %H:%M')}",
        "-" * 72,
        f"Toplam kayıt: {d['total_records']} | Personel: {d['total_employees']} | Kurşun ölçümü: {d['total_lead']}",
        f">=30: {len(d['over30'])} ({d['pct30']}%) | >=40: {len(d['over40'])} ({d['pct40']}%) | >=45: {len(d['over45'])} ({d['pct45']}%)",
        "",
        "Kurşun aralıkları:",
    ]
    for r in d["ranges"]:
        lines.append(f"  {r['label']}: {r['count']}")
    lines.append("")
    lines.append(f"Odyometri takip: {len(d['odyo_follow'])}")
    for x in d["odyo_follow"][:30]:
        lines.append(f"  - {x['employee_name']} | {x['job_title'] or '—'}")
    lines.append(f"SFT takip: {len(d['sft_follow'])}")
    for x in d["sft_follow"][:30]:
        lines.append(f"  - {x['employee_name']} | {x['job_title'] or '—'}")
    lines.append(f"Akciğer takip: {len(d['chest_follow'])}")
    for x in d["chest_follow"][:30]:
        lines.append(f"  - {x['employee_name']} | {x['job_title'] or '—'}")
    lines.append(f"Kurşun maruziyeti var, değer yok: {len(d['missing_lead'])}")
    for x in d["missing_lead"][:30]:
        lines.append(f"  - {x['employee_name']} | {x['job_title'] or '—'}")
    lines.append(f"Sağlık kaydı eksik personel: {len(d['missing_employees'])}")
    for x in d["missing_employees"][:50]:
        lines.append(f"  - {x['full_name']} | {x.get('job_title') or '—'} | {x.get('department') or '—'}")
    body = "\n".join(lines) + "\n"
    append_health_access(
        db, actor=user, company_id=effective, action="analysis_export", request=request,
        metadata={"format": "txt", "record_count": len(records)},
    )
    db.commit()
    return PlainTextResponse(
        body,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="saglik-analiz-raporu.txt"'},
    )


@router.get("", response_model=list[HealthRecordResponse])
def list_health_records(
    request: Request,
    company_id: int | None = None,
    employee_id: int | None = None,
    record_type: HealthRecordType | None = None,
    fitness_status: HealthFitnessStatus | None = None,
    overdue_only: bool = False,
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*HEALTH_SUPPORT_ROLES)),
):
    query = _active().order_by(HealthRecord.examination_date.desc(), HealthRecord.id.desc())
    company_ids = company_ids_for_query(db, user, company_id)
    if company_ids == []:
        return []
    if company_ids is not None:
        query = query.where(HealthRecord.company_id.in_(company_ids))
    if employee_id:
        query = query.where(HealthRecord.employee_id == employee_id)
    if record_type:
        query = query.where(HealthRecord.record_type == record_type)
    if fitness_status:
        if user.role not in PHYSICIAN_ROLES:
            raise HTTPException(
                status_code=403,
                detail="Uygunluk kararı filtresi yalnızca işyeri hekimine açıktır.",
            )
        query = query.where(HealthRecord.fitness_status == fitness_status)
    rows = list(db.scalars(query).all())
    employees = _employees_map(db, {r.employee_id for r in rows})
    today = date.today()
    include_conf = user.role in PHYSICIAN_ROLES
    out = []
    for r in rows:
        emp = employees.get(r.employee_id)
        if q:
            needle = q.casefold()
            view = DecryptedRecordView(r)
            hay = f"{emp.full_name if emp else ''} {r.physician_name or ''}".casefold()
            if include_conf:
                hay = f"{hay} {view.summary or ''}".casefold()
            if needle not in hay:
                continue
        if overdue_only and not (r.next_examination_date and r.next_examination_date < today):
            continue
        out.append(_to_response(r, emp, include_conf))
    counts: dict[int, int] = {}
    for row in out:
        counts[row.company_id] = counts.get(row.company_id, 0) + 1
    for cid in company_ids or []:
        append_health_access(
            db, actor=user, company_id=cid, action="record_list", request=request,
            metadata={"returned_count": counts.get(cid, 0), "masked": not include_conf},
        )
    db.commit()
    return out


@router.post("", response_model=HealthRecordResponse)
def create_health_record(
    request: Request,
    payload: HealthRecordCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*HEALTH_SUPPORT_ROLES)),
):
    ensure_access(db, user, payload.company_id)
    employee = db.get(Employee, payload.employee_id)
    if not employee or employee.company_id != payload.company_id:
        raise HTTPException(status_code=400, detail="Personel ve firma eşleşmiyor.")
    company = db.get(Company, payload.company_id)
    _validate_periodic_exam_ceiling(
        record_type=payload.record_type,
        examination_date=payload.examination_date,
        next_examination_date=payload.next_examination_date,
        hazard_class=company.hazard_class if company else None,
        special_status=employee.special_status,
    )
    supplied_fields = {
        field for field in payload.model_fields_set
        if getattr(payload, field, None) is not None
    }
    _enforce_write_matrix(user, supplied_fields, create=True)
    physician = _resolve_assigned_physician(
        db,
        user=user,
        company_id=payload.company_id,
        requested_id=payload.physician_professional_id,
    )
    data = payload.model_dump(exclude_unset=True)
    if user.role == UserRole.OTHER_HEALTH_PERSONNEL:
        data = {key: value for key, value in data.items() if key in DSP_CREATE_FIELDS}
    data.pop("physician_name", None)
    data.pop("physician_professional_id", None)
    if not data.get("informed_consent"):
        raise HTTPException(status_code=400, detail="Personel bilgilendirme onayı zorunludur (Pro sağlık formu).")
    data["informed_consent_at"] = datetime.utcnow()
    if not data.get("next_examination_date"):
        data["next_examination_date"] = default_next_exam(
            payload.examination_date,
            company.hazard_class if company else None,
            employee.special_status if payload.record_type == HealthRecordType.PERIODIC_EXAM else None,
        )
    if user.role == UserRole.WORKPLACE_PHYSICIAN and not data.get("suggested_tests") and not data.get("exposures"):
        sug = suggest_for_job(employee.job_title, employee.department)
        data["suggested_tests"] = data.get("suggested_tests") or ", ".join(sug["suggested_tests"])
        data["exposures"] = data.get("exposures") or ", ".join(sug["exposures"])
    # None alanları atla — eksik DB kolonlarında gereksiz INSERT riskini azaltır
    data = {k: v for k, v in data.items() if v is not None}
    data = encrypt_payload(data)
    try:
        # Aynı personel + tür + tarih için çift kayıt engeli (Pro)
        dup = db.scalar(
            _active().where(
                HealthRecord.company_id == payload.company_id,
                HealthRecord.employee_id == payload.employee_id,
                HealthRecord.record_type == payload.record_type,
                HealthRecord.examination_date == payload.examination_date,
            )
        )
        if dup:
            raise HTTPException(
                status_code=400,
                detail="Aynı personel, muayene türü ve tarih için kayıt zaten var.",
            )
        if user.role == UserRole.OTHER_HEALTH_PERSONNEL:
            data["fitness_status"] = HealthFitnessStatus.PENDING
        record = HealthRecord(
            **data,
            physician_professional_id=physician.id,
            physician_name=physician.full_name,
            created_by_id=user.id,
            version=1,
        )
        _apply_lead_eval(record)
        db.add(record)
        db.flush()
        append_health_revision(
            db,
            record=record,
            actor=user,
            action="create",
            reason="Sağlık kaydı oluşturuldu.",
        )
        append_health_access(
            db, actor=user, company_id=record.company_id, record_id=record.id,
            action="record_create", request=request,
        )
        db.commit()
        db.refresh(record)
        return _to_response(record, employee, user.role in PHYSICIAN_ROLES)
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Sağlık kaydı kaydedilemedi: {exc}") from exc


@router.get("/export.txt")
def export_health_txt(
    request: Request,
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*PHYSICIAN_ONLY)),
):
    effective = effective_company_id(db, user, company_id)
    company = db.get(Company, effective)
    rows = _company_records(db, effective)
    employees = _employees_map(db, {r.employee_id for r in rows})
    lines = [
        "İSG Suite OSGB — Sağlık Gözetimi",
        f"Firma: {company.name if company else effective}",
        f"Olusturma: {datetime.utcnow().strftime('%d.%m.%Y %H:%M')}",
        "-" * 72,
    ]
    for r in rows:
        emp = employees.get(r.employee_id)
        name = emp.full_name if emp else f"#{r.employee_id}"
        view = DecryptedRecordView(r)
        lines.append(
            f"{r.examination_date} | {RECORD_TYPE_LABELS.get(r.record_type, r.record_type.value)} | "
            f"{name} | Hekim: {r.physician_name or '—'} | "
            f"Durum: {FITNESS_LABELS.get(r.fitness_status, r.fitness_status.value)} | "
            f"Sonraki: {r.next_examination_date or '—'}"
        )
        lines.append(f"   Özet: {smart_summary(view, emp)}")
        tetkik = []
        if view.audiometry_result or r.audiometry_date:
            tetkik.append(f"Odyo:{view.audiometry_result or r.audiometry_date}")
        if view.spirometry_result or r.spirometry_date:
            tetkik.append(f"SFT:{view.spirometry_result or r.spirometry_date}")
        if view.chest_xray_result or r.chest_xray_date:
            tetkik.append(f"Akciger:{view.chest_xray_result or r.chest_xray_date}")
        if r.blood_lead_value is not None:
            tetkik.append(f"Pb:{r.blood_lead_value}{r.blood_lead_unit or ''} ({r.blood_lead_eval or '—'})")
        if tetkik:
            lines.append(f"   Tetkik: {' | '.join(tetkik)}")
        if view.summary:
            lines.append(f"   Not: {view.summary}")
    body = "\n".join(lines) + "\n"
    append_health_access(
        db, actor=user, company_id=effective, action="records_export", request=request,
        metadata={"format": "txt", "record_count": len(rows)},
    )
    db.commit()
    return PlainTextResponse(
        body,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="saglik-gozetimi.txt"'},
    )


@router.get("/export.xlsx")
def export_health_xlsx(
    request: Request,
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*PHYSICIAN_ONLY)),
):
    effective = effective_company_id(db, user, company_id)
    company = db.get(Company, effective)
    rows = _company_records(db, effective)
    employees = _employees_map(db, {r.employee_id for r in rows})
    wb = Workbook()
    ws = wb.active
    ws.title = "Sağlık Gözetimi"
    headers = [
        "Personel", "Görev", "Bölüm", "Muayene Türü", "Muayene Tarihi", "Sonraki Muayene",
        "Durum", "Hekim", "Odyometri", "SFT", "Akciğer", "Kan Kurşun", "Kurşun Değerlendirme",
        "Önerilen Tetkikler", "Maruziyetler", "Diğer Biyolojik", "Akıllı Özet", "Rapor Dosyası",
    ]
    ws.append(headers)
    for r in rows:
        emp = employees.get(r.employee_id)
        view = DecryptedRecordView(r)
        ws.append([
            emp.full_name if emp else f"#{r.employee_id}",
            emp.job_title if emp else "",
            emp.department if emp else "",
            RECORD_TYPE_LABELS.get(r.record_type, r.record_type.value),
            r.examination_date.isoformat() if r.examination_date else "",
            r.next_examination_date.isoformat() if r.next_examination_date else "",
            FITNESS_LABELS.get(r.fitness_status, r.fitness_status.value),
            r.physician_name or "",
            f"{r.audiometry_date or ''} / {view.audiometry_result or ''}".strip(" /"),
            f"{r.spirometry_date or ''} / {view.spirometry_result or ''}".strip(" /"),
            f"{r.chest_xray_date or ''} / {view.chest_xray_result or ''}".strip(" /"),
            f"{r.blood_lead_value if r.blood_lead_value is not None else ''} {r.blood_lead_unit or ''}".strip(),
            r.blood_lead_eval or "",
            view.suggested_tests or "",
            view.exposures or "",
            view.other_biological_test or "",
            smart_summary(view, emp),
            r.report_file_name or "",
        ])
    # Analiz sayfası
    all_emps = list(
        db.scalars(
            select(Employee).where(Employee.company_id == effective, Employee.is_active.is_(True))
        ).all()
    )
    analysis = build_analysis_payload(rows, employees, all_employees=all_emps)
    wa = wb.create_sheet("Analiz")
    wa.append(["Firma", company.name if company else effective])
    wa.append(["Kurşun ölçümü", analysis["total_lead"]])
    wa.append([">=30", len(analysis["over30"]), f"%{analysis['pct30']}"])
    wa.append([">=40", len(analysis["over40"]), f"%{analysis['pct40']}"])
    wa.append([">=45", len(analysis["over45"]), f"%{analysis['pct45']}"])
    wa.append([])
    wa.append(["Eksik personel (sağlık kaydı yok)"])
    wa.append(["Ad Soyad", "Görev", "Bölüm"])
    for e in analysis["missing_employees"]:
        wa.append([e["full_name"], e.get("job_title") or "", e.get("department") or ""])
    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    append_health_access(
        db, actor=user, company_id=effective, action="records_export", request=request,
        metadata={"format": "xlsx", "record_count": len(rows)},
    )
    db.commit()
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="saglik-gozetimi-{effective}.xlsx"'},
    )


@router.get("/audit/{record_id}/revisions")
def health_record_revisions(
    request: Request,
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*PHYSICIAN_ONLY)),
):
    record = db.get(HealthRecord, record_id)
    if not record:
        raise HTTPException(404, "Sağlık kaydı bulunamadı.")
    ensure_access(db, user, record.company_id)
    rows = list(
        db.scalars(
            select(HealthRecordRevision)
            .where(HealthRecordRevision.record_id == record_id)
            .order_by(HealthRecordRevision.version, HealthRecordRevision.id)
        ).all()
    )
    result = {
        "record_id": record_id,
        "integrity_valid": verify_revision_chain(rows),
        "items": [
            {
                "id": row.id,
                "version": row.version,
                "action": row.action,
                "actor_user_id": row.actor_user_id,
                "reason": row.reason,
                "previous_hash": row.previous_hash,
                "entry_hash": row.entry_hash,
                "created_at": row.created_at,
            }
            for row in rows
        ],
    }
    append_health_access(
        db, actor=user, company_id=record.company_id, record_id=record.id,
        action="revision_log_view", request=request,
    )
    db.commit()
    return result


@router.get("/audit/{record_id}/access-log")
def health_record_access_log(
    request: Request,
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*PHYSICIAN_ONLY)),
):
    record = db.get(HealthRecord, record_id)
    if not record:
        raise HTTPException(404, "Sağlık kaydı bulunamadı.")
    ensure_access(db, user, record.company_id)
    company_rows = list(
        db.scalars(
            select(HealthAccessLog)
            .where(HealthAccessLog.company_id == record.company_id)
            .order_by(HealthAccessLog.id)
        ).all()
    )
    rows = [row for row in company_rows if row.record_id == record_id]
    result = {
        "record_id": record_id,
        "integrity_valid": verify_access_chain(company_rows),
        "items": [
            {
                "id": row.id,
                "actor_user_id": row.actor_user_id,
                "action": row.action,
                "purpose": row.purpose,
                "request_path": row.request_path,
                "ip_address": row.ip_address,
                "entry_hash": row.entry_hash,
                "created_at": row.created_at,
            }
            for row in rows
        ],
    }
    append_health_access(
        db, actor=user, company_id=record.company_id, record_id=record.id,
        action="access_log_view", request=request,
    )
    db.commit()
    return result


@router.patch("/{record_id}", response_model=HealthRecordResponse)
def update_health_record(
    request: Request,
    record_id: int,
    payload: HealthRecordUpdate,
    change_reason: str = Query(default="Sağlık kaydı güncellendi.", min_length=5, max_length=500),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*HEALTH_SUPPORT_ROLES)),
):
    record = db.get(HealthRecord, record_id)
    if not record or record.deleted_at:
        raise HTTPException(404, "Sağlık kaydı bulunamadı.")
    ensure_access(db, user, record.company_id)
    company = db.get(Company, record.company_id)
    schedule_employee = db.get(Employee, record.employee_id)
    date_fields = {"examination_date", "next_examination_date"} & payload.model_fields_set
    if date_fields:
        _validate_health_date_pair(
            examination_date=(
                payload.examination_date
                if "examination_date" in date_fields
                else record.examination_date
            ),
            next_examination_date=(
                payload.next_examination_date
                if "next_examination_date" in date_fields
                else record.next_examination_date
            ),
        )
    _validate_periodic_exam_ceiling(
        record_type=(
            payload.record_type
            if "record_type" in payload.model_fields_set and payload.record_type is not None
            else record.record_type
        ),
        examination_date=(
            payload.examination_date
            if "examination_date" in payload.model_fields_set and payload.examination_date is not None
            else record.examination_date
        ),
        next_examination_date=(
            payload.next_examination_date
            if "next_examination_date" in payload.model_fields_set
            else record.next_examination_date
        ),
        hazard_class=company.hazard_class if company else None,
        special_status=schedule_employee.special_status if schedule_employee else None,
    )
    supplied_fields = {
        field for field in payload.model_fields_set
        if getattr(payload, field, None) is not None
    }
    _enforce_write_matrix(user, supplied_fields, create=False)
    if user.role == UserRole.WORKPLACE_PHYSICIAN:
        physician = _resolve_assigned_physician(
            db,
            user=user,
            company_id=record.company_id,
            requested_id=payload.physician_professional_id,
        )
        if record.physician_professional_id not in (None, physician.id):
            raise HTTPException(403, "Bu klinik kayıt başka bir işyeri hekimi tarafından oluşturulmuştur.")
    else:
        physician = None
        if record.fitness_status != HealthFitnessStatus.PENDING:
            raise HTTPException(403, "DSP yalnız hekim tarafından sonuçlandırılmamış kayıtları güncelleyebilir.")
        if "physician_professional_id" in supplied_fields:
            physician = _resolve_assigned_physician(
                db,
                user=user,
                company_id=record.company_id,
                requested_id=payload.physician_professional_id,
            )
    updates = payload.model_dump(exclude_unset=True)
    if user.role == UserRole.OTHER_HEALTH_PERSONNEL:
        updates = {key: value for key, value in updates.items() if key in DSP_UPDATE_FIELDS}
    updates.pop("physician_name", None)
    updates.pop("physician_professional_id", None)
    if "informed_consent" in updates:
        if updates["informed_consent"]:
            if not record.informed_consent_at:
                updates["informed_consent_at"] = datetime.utcnow()
        else:
            updates["informed_consent_at"] = None
    updates = encrypt_payload(updates)
    for k, v in updates.items():
        setattr(record, k, v)
    if physician is not None:
        record.physician_professional_id = physician.id
        record.physician_name = physician.full_name
    _apply_lead_eval(record)
    record.version = int(record.version or 1) + 1
    record.updated_at = datetime.utcnow()
    append_health_revision(
        db, record=record, actor=user, action="update", reason=change_reason,
    )
    append_health_access(
        db, actor=user, company_id=record.company_id, record_id=record.id,
        action="record_update", request=request,
    )
    db.commit()
    db.refresh(record)
    employee = db.get(Employee, record.employee_id)
    return _to_response(record, employee, user.role in PHYSICIAN_ROLES)


@router.delete("/{record_id}")
def delete_health_record(
    request: Request,
    record_id: int,
    reason: str = Query(min_length=5, max_length=500),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*PHYSICIAN_ONLY)),
):
    record = db.get(HealthRecord, record_id)
    if not record or record.deleted_at:
        raise HTTPException(404, "Sağlık kaydı bulunamadı.")
    ensure_access(db, user, record.company_id)
    physician = _resolve_assigned_physician(
        db, user=user, company_id=record.company_id, requested_id=None,
    )
    if record.physician_professional_id not in (None, physician.id):
        raise HTTPException(403, "Bu klinik kayıt başka bir işyeri hekimi tarafından oluşturulmuştur.")
    record.deleted_at = datetime.utcnow()
    record.updated_at = datetime.utcnow()
    record.version = int(record.version or 1) + 1
    append_health_revision(db, record=record, actor=user, action="delete", reason=reason)
    append_health_access(
        db, actor=user, company_id=record.company_id, record_id=record.id,
        action="record_delete", request=request,
    )
    db.commit()
    return {"ok": True, "id": record_id}


@router.get("/{record_id}/form.html", response_class=HTMLResponse)
def health_form_html(
    request: Request,
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*PHYSICIAN_ONLY)),
):
    record = db.get(HealthRecord, record_id)
    if not record or record.deleted_at:
        raise HTTPException(404, "Sağlık kaydı bulunamadı.")
    ensure_access(db, user, record.company_id)
    company = db.get(Company, record.company_id)
    employee = db.get(Employee, record.employee_id)
    view = DecryptedRecordView(record)
    is_physician = True
    is_ek2_record = record.record_type in (
        HealthRecordType.ENTRY_EXAM,
        HealthRecordType.PERIODIC_EXAM,
    )
    document_heading = (
        "İşe Giriş / Periyodik Muayene Formu — Gizli Klinik Sağlık Dosyası"
        if is_ek2_record
        else "Gizli Klinik Sağlık Dosyası"
    )
    document_note = (
        "EK-2 kapsamında işyeri hekimi kaydı"
        if is_ek2_record
        else "Klinik sağlık gözetimi kaydı"
    )
    conf = view.confidential_note if is_physician else None
    # P0-07: form HTML'de klinik metin yalnız hekim/GA
    audiometry_txt = view.audiometry_result if is_physician else None
    spirometry_txt = view.spirometry_result if is_physician else None
    chest_txt = view.chest_xray_result if is_physician else None
    other_bio = view.other_biological_test if is_physician else None
    suggested = view.suggested_tests if is_physician else None
    exposures = view.exposures if is_physician else None
    summary_txt = view.summary if is_physician else None
    follow_up = view.follow_up_note if is_physician else None
    restrictions_txt = view.restrictions if is_physician else None
    smart = smart_summary(view, employee) if is_physician else ""
    consent_txt = "Evet" if record.informed_consent else "Hayır"
    if record.informed_consent_at:
        consent_txt += f" ({record.informed_consent_at.strftime('%d.%m.%Y %H:%M')})"

    def safe(value) -> str:
        if value is None:
            return ""
        return html_escape(str(value), quote=True)

    def cell(label: str, value: str) -> str:
        return (
            f"<div class='box'><div class='lab'>{safe(label)}</div>"
            f"<div class='val'>{safe(value) or '—'}</div></div>"
        )

    company_name = safe(company.name if company else "")
    employee_name = safe(employee.full_name if employee else "")
    html = f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<title>{safe(document_heading)}</title>
<style>
body{{margin:0;background:#eef2f7;font-family:Segoe UI,Arial,sans-serif;color:#0f172a}}
.top{{background:#0f2744;color:#fff;padding:18px 28px}}
.wrap{{max-width:920px;margin:18px auto;background:#fff;border-radius:12px;padding:22px;box-shadow:0 8px 24px #0f172a14}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.box{{border:1px solid #dbe3ee;border-radius:10px;padding:10px 12px}}
.lab{{font-size:12px;color:#64748b;margin-bottom:4px}}
.val{{font-size:14px;font-weight:600}}
h2{{margin:0 0 8px}} h3{{margin:18px 0 8px;color:#0f2744}}
.sign{{display:flex;justify-content:space-between;margin-top:36px;gap:24px}}
.sign div{{flex:1;text-align:center;border-top:1px solid #94a3b8;padding-top:10px;font-size:13px}}
@media print{{body{{background:#fff}}.wrap{{box-shadow:none;margin:0;max-width:none}}}}
</style></head><body>
<div class="top"><h2>{safe(document_heading)}</h2>
<p style="margin:0;opacity:.9">{safe(document_note)} · Yalnız işyeri hekimi erişimine açıktır · {company_name} · {employee_name}</p></div>
<div class="wrap">
<div class="grid">
{cell('Personel', employee.full_name if employee else '')}
{cell('Görev', employee.job_title if employee else '')}
{cell('Bölüm', employee.department if employee else '')}
{cell('Muayene Türü', RECORD_TYPE_LABELS.get(record.record_type, record.record_type.value))}
{cell('Muayene Tarihi', str(record.examination_date or ''))}
{cell('Sonraki Muayene', str(record.next_examination_date or ''))}
{cell('İşyeri Hekimi', record.physician_name or '')}
{cell('Uygunluk', FITNESS_LABELS.get(record.fitness_status, record.fitness_status.value))}
{cell('Bilgilendirme Onayı', consent_txt)}
</div>
<h3>Tetkikler</h3>
<div class="grid">
{cell('Odyometri', f"{record.audiometry_date or ''} / {audiometry_txt or ''}".strip(' /'))}
{cell('SFT', f"{record.spirometry_date or ''} / {spirometry_txt or ''}".strip(' /'))}
{cell('Akciğer Grafisi', f"{record.chest_xray_date or ''} / {chest_txt or ''}".strip(' /'))}
{cell('Kan Kurşun', f"{record.blood_lead_date or ''} / {record.blood_lead_value if record.blood_lead_value is not None else ''} {record.blood_lead_unit or ''} (ref {record.blood_lead_ref or '—'}) / {record.blood_lead_eval or ''}".strip(' /'))}
{cell('Diğer Biyolojik Tetkik', other_bio or '')}
{cell('Akıllı Özet', smart)}
</div>
<h3>Önerilen tetkikler / Maruziyet</h3>
<p>{safe(suggested) or '—'}</p>
<p>{safe(exposures) or '—'}</p>
<h3>Not / Kısıt / Takip</h3>
<p><strong>Özet:</strong> {safe(summary_txt) or '—'}</p>
<p><strong>Kısıtlamalar:</strong> {safe(restrictions_txt) or '—'}</p>
<p><strong>Takip:</strong> {safe(follow_up) or ''}</p>
{f'<h3>Gizli hekim notu</h3><p>{safe(conf)}</p>' if conf else ''}
<div class="sign">
<div>İşyeri Hekimi<br><b>{safe(record.physician_name) or '........................'}</b></div>
</div>
<p style="margin-top:18px;font-size:12px;color:#64748b">Yazdır: Ctrl+P · İSG Suite OSGB</p>
</div></body></html>"""
    append_health_access(
        db, actor=user, company_id=record.company_id, record_id=record.id,
        action="clinical_form_view", request=request,
    )
    db.commit()
    return HTMLResponse(html)


@router.get("/{record_id}/fitness.html", response_class=HTMLResponse)
def health_fitness_html(
    request: Request,
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*PHYSICIAN_ONLY)),
):
    """Employer-facing minimum-necessary fitness document; no clinical findings."""
    record = db.get(HealthRecord, record_id)
    if not record or record.deleted_at:
        raise HTTPException(404, "Sağlık kaydı bulunamadı.")
    ensure_access(db, user, record.company_id)
    if record.fitness_status == HealthFitnessStatus.PENDING:
        raise HTTPException(409, "Hekim uygunluk kararını tamamlamadan işveren belgesi oluşturulamaz.")
    company = db.get(Company, record.company_id)
    employee = db.get(Employee, record.employee_id)
    view = DecryptedRecordView(record)
    revision = db.scalar(
        select(HealthRecordRevision)
        .where(HealthRecordRevision.record_id == record.id)
        .order_by(HealthRecordRevision.version.desc())
        .limit(1)
    )

    def safe(value) -> str:
        return html_escape(str(value), quote=True) if value is not None else ""

    verification = (revision.entry_hash[:16].upper() if revision else "KAYIT-BEKLIYOR")
    html = f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<title>İşe Uygunluk ve Çalışma Kısıtları Belgesi</title>
<style>
body{{margin:0;background:#eef2f7;font-family:Segoe UI,Arial,sans-serif;color:#0f172a}}
.top{{background:#0f2744;color:#fff;padding:18px 28px}}
.wrap{{max-width:820px;margin:18px auto;background:#fff;border-radius:12px;padding:26px;box-shadow:0 8px 24px #0f172a14}}
.grid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.box{{border:1px solid #dbe3ee;border-radius:10px;padding:12px}} .lab{{font-size:12px;color:#64748b}} .val{{font-weight:700;margin-top:4px}}
.notice{{margin-top:18px;padding:12px;border:1px solid #99f6e4;background:#f0fdfa;border-radius:10px;font-size:13px}}
.sign{{margin:42px 0 10px auto;width:48%;text-align:center;border-top:1px solid #94a3b8;padding-top:10px}}
@media print{{body{{background:#fff}}.wrap{{box-shadow:none;margin:0;max-width:none}}}}
</style></head><body>
<div class="top"><h2>İşe Uygunluk ve Çalışma Kısıtları Belgesi</h2><p style="margin:0;opacity:.9">İşverene sunulacak asgari bilgi belgesi</p></div>
<div class="wrap"><div class="grid">
<div class="box"><div class="lab">İşyeri</div><div class="val">{safe(company.name if company else '')}</div></div>
<div class="box"><div class="lab">Çalışan</div><div class="val">{safe(employee.full_name if employee else '')}</div></div>
<div class="box"><div class="lab">Görevi / Bölümü</div><div class="val">{safe(' / '.join(x for x in ((employee.job_title if employee else None), (employee.department if employee else None)) if x))}</div></div>
<div class="box"><div class="lab">Muayene Tarihi</div><div class="val">{safe(record.examination_date)}</div></div>
<div class="box"><div class="lab">İşe Uygunluk</div><div class="val">{safe(FITNESS_LABELS.get(record.fitness_status, record.fitness_status.value))}</div></div>
<div class="box"><div class="lab">Sonraki Muayene</div><div class="val">{safe(record.next_examination_date) or '—'}</div></div>
</div>
<h3>Çalışma Kısıtları / Uygunluk Şartları</h3><p>{safe(view.restrictions) or 'Kısıtlama bildirilmemiştir.'}</p>
<div class="notice">Bu belge tanı, tetkik sonucu, klinik not veya sağlık geçmişi içermez. Ayrıntılı klinik dosya gizlidir ve yalnız işyeri hekimi erişimindedir.</div>
<div class="sign">İşyeri Hekimi<br><b>{safe(record.physician_name) or '........................'}</b></div>
<p style="font-size:11px;color:#64748b">Kayıt sürümü: {record.version} · Doğrulama: {verification}</p>
</div></body></html>"""
    append_health_access(
        db, actor=user, company_id=record.company_id, record_id=record.id,
        action="fitness_document_view", request=request,
        metadata={"record_version": record.version},
    )
    db.commit()
    return HTMLResponse(html)


@router.post("/{record_id}/report", response_model=HealthRecordResponse)
async def upload_health_report(
    request: Request,
    record_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*HEALTH_SUPPORT_ROLES)),
):
    record = db.get(HealthRecord, record_id)
    if not record or record.deleted_at:
        raise HTTPException(404, "Sağlık kaydı bulunamadı.")
    ensure_access(db, user, record.company_id)
    name = file.filename or "saglik-raporu.pdf"
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_REPORT:
        raise HTTPException(422, "Sadece pdf, jpg, png veya docx yükleyin.")
    data = await file.read()
    if not data:
        raise HTTPException(400, "Boş dosya yüklenemez.")
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Dosya {settings.max_upload_mb} MB sınırını aşıyor.")
    safe_mime = {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }.get(ext, "application/octet-stream")
    if record.report_storage_path:
        old = (_upload_root() / record.report_storage_path).resolve()
        if _upload_root() in old.parents and old.exists():
            try:
                from app.services.archive_store import archive_file_before_delete

                archive_file_before_delete(
                    db,
                    source=old,
                    user=user,
                    company_id=record.company_id,
                    entity_type="health_report",
                    entity_id=str(record.id),
                    original_name=record.report_file_name,
                    notes="Sağlık raporu değiştirilmeden önce arşivlendi",
                )
            except Exception:
                logger.warning(
                    "health report: archive-before-replace failed id=%s",
                    record.id,
                    exc_info=True,
                )
            delete_relative(record.report_storage_path)
    rel = f"{record.company_id}/health/{record.id}_{uuid4().hex[:10]}{ext}"
    if settings.upload_gateway_enabled:
        persist_relative(data, relative_path=rel, original_name=name)
    else:
        assert_safe_upload(data, ext, name)
        target = _upload_root() / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    record.report_file_name = Path(name).name
    record.report_storage_path = rel.replace("\\", "/")
    record.report_content_type = safe_mime
    record.version = int(record.version or 1) + 1
    record.updated_at = datetime.utcnow()
    append_health_revision(
        db,
        record=record,
        actor=user,
        action="report_upload",
        reason="Sağlık raporu dosyası eklendi veya yenilendi.",
    )
    append_health_access(
        db,
        actor=user,
        company_id=record.company_id,
        record_id=record.id,
        action="report_upload",
        request=request,
        metadata={"content_type": safe_mime},
    )
    db.commit()
    db.refresh(record)
    employee = db.get(Employee, record.employee_id)
    return _to_response(record, employee, user.role in PHYSICIAN_ROLES)


@router.get("/{record_id}/report")
def download_health_report(
    request: Request,
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*PHYSICIAN_ONLY)),
):
    from app.services.stored_files import response_for_storage_key

    record = db.get(HealthRecord, record_id)
    if not record or record.deleted_at:
        raise HTTPException(404, "Sağlık kaydı bulunamadı.")
    ensure_access(db, user, record.company_id)
    if not record.report_storage_path:
        raise HTTPException(404, "Rapor dosyası yok.")
    append_health_access(
        db,
        actor=user,
        company_id=record.company_id,
        record_id=record.id,
        action="report_download",
        request=request,
        metadata={"content_type": record.report_content_type},
    )
    db.commit()
    return response_for_storage_key(
        record.report_storage_path,
        filename=record.report_file_name,
        media_type=record.report_content_type or "application/octet-stream",
    )
