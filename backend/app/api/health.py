"""Sağlık gözetimi API — İSG PRO 2026 Sağlık Gözetimi / Analiz parity."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from io import BytesIO
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse
from openpyxl import Workbook
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.company_access import company_ids_for_query, effective_company_id, ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.database import get_db
from app.models.entities import Company, Employee, HealthFitnessStatus, HealthRecord, HealthRecordType, User, UserRole
from app.schemas.health import HealthRecordCreate, HealthRecordResponse, HealthRecordUpdate
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

router = APIRouter(prefix="/health-records", tags=["Sağlık Kayıtları"])

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
ALLOWED_REPORT = {".pdf", ".jpg", ".jpeg", ".png", ".docx"}

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


def ensure_access(db: Session, user: User, company_id: int) -> None:
    ensure_company_access(db, user, company_id)


def _upload_root() -> Path:
    return Path(settings.upload_dir).resolve()


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
    data.has_report = bool(row.report_storage_path)
    data.smart_summary = smart_summary(row, employee)
    data.tetkik_summary = tetkik_summary(row)
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
def health_meta():
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


@router.get("/suggest")
def health_suggest(
    job_title: str | None = None,
    department: str | None = None,
    user: User = Depends(require_roles(*HEALTH_ROLES)),
):
    _ = user
    return suggest_for_job(job_title, department)


@router.get("/lead-eval")
def health_lead_eval(
    value: float | None = None,
    ref: float | None = 30,
    user: User = Depends(require_roles(*HEALTH_ROLES)),
):
    _ = user
    code = evaluate_blood_lead(value, ref)
    labels = {"normal": "Normal", "izlem": "İzlem", "yuksek": "Yüksek", "kritik": "Kritik"}
    return {"code": code, "label": labels.get(code or "", "—"), "value": value, "ref": ref}


@router.get("/summary")
def health_summary(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*HEALTH_ROLES)),
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
    return {
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


@router.get("/analysis")
def health_analysis(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*HEALTH_ROLES)),
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
    return payload


@router.get("/analysis.txt")
def health_analysis_txt(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*HEALTH_ROLES)),
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
    return PlainTextResponse(
        body,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="saglik-analiz-raporu.txt"'},
    )


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
    ensure_access(db, user, payload.company_id)
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
        lines.append(
            f"{r.examination_date} | {RECORD_TYPE_LABELS.get(r.record_type, r.record_type.value)} | "
            f"{name} | Hekim: {r.physician_name or '—'} | "
            f"Durum: {FITNESS_LABELS.get(r.fitness_status, r.fitness_status.value)} | "
            f"Sonraki: {r.next_examination_date or '—'}"
        )
        lines.append(f"   Özet: {smart_summary(r, emp)}")
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
            lines.append(f"   Not: {r.summary}")
    body = "\n".join(lines) + "\n"
    return PlainTextResponse(
        body,
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="saglik-gozetimi.txt"'},
    )


@router.get("/export.xlsx")
def export_health_xlsx(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*HEALTH_ROLES)),
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
        ws.append([
            emp.full_name if emp else f"#{r.employee_id}",
            emp.job_title if emp else "",
            emp.department if emp else "",
            RECORD_TYPE_LABELS.get(r.record_type, r.record_type.value),
            r.examination_date.isoformat() if r.examination_date else "",
            r.next_examination_date.isoformat() if r.next_examination_date else "",
            FITNESS_LABELS.get(r.fitness_status, r.fitness_status.value),
            r.physician_name or "",
            f"{r.audiometry_date or ''} / {r.audiometry_result or ''}".strip(" /"),
            f"{r.spirometry_date or ''} / {r.spirometry_result or ''}".strip(" /"),
            f"{r.chest_xray_date or ''} / {r.chest_xray_result or ''}".strip(" /"),
            f"{r.blood_lead_value if r.blood_lead_value is not None else ''} {r.blood_lead_unit or ''}".strip(),
            r.blood_lead_eval or "",
            r.suggested_tests or "",
            r.exposures or "",
            r.other_biological_test or "",
            smart_summary(r, emp),
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
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="saglik-gozetimi-{effective}.xlsx"'},
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
    ensure_access(db, user, record.company_id)
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
    ensure_access(db, user, record.company_id)
    record.deleted_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "id": record_id}


@router.get("/{record_id}/form.html", response_class=HTMLResponse)
def health_form_html(
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*HEALTH_ROLES)),
):
    record = db.get(HealthRecord, record_id)
    if not record or record.deleted_at:
        raise HTTPException(404, "Sağlık kaydı bulunamadı.")
    ensure_access(db, user, record.company_id)
    company = db.get(Company, record.company_id)
    employee = db.get(Employee, record.employee_id)
    conf = record.confidential_note if user.role in PHYSICIAN_ROLES else None

    def cell(label: str, value: str) -> str:
        return (
            f"<div class='box'><div class='lab'>{label}</div>"
            f"<div class='val'>{value or '—'}</div></div>"
        )

    html = f"""<!doctype html><html lang="tr"><head><meta charset="utf-8">
<title>Sağlık Gözetimi Formu</title>
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
<div class="top"><h2>Sağlık Gözetimi Formu</h2>
<p style="margin:0;opacity:.9">{company.name if company else ''} · {employee.full_name if employee else ''}</p></div>
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
</div>
<h3>Tetkikler</h3>
<div class="grid">
{cell('Odyometri', f"{record.audiometry_date or ''} / {record.audiometry_result or ''}".strip(' /'))}
{cell('SFT', f"{record.spirometry_date or ''} / {record.spirometry_result or ''}".strip(' /'))}
{cell('Akciğer Grafisi', f"{record.chest_xray_date or ''} / {record.chest_xray_result or ''}".strip(' /'))}
{cell('Kan Kurşun', f"{record.blood_lead_date or ''} / {record.blood_lead_value if record.blood_lead_value is not None else ''} {record.blood_lead_unit or ''} (ref {record.blood_lead_ref or '—'}) / {record.blood_lead_eval or ''}".strip(' /'))}
{cell('Diğer Biyolojik Tetkik', record.other_biological_test or '')}
{cell('Akıllı Özet', smart_summary(record, employee))}
</div>
<h3>Önerilen tetkikler / Maruziyet</h3>
<p>{record.suggested_tests or '—'}</p>
<p>{record.exposures or '—'}</p>
<h3>Not / Kısıt / Takip</h3>
<p>{record.summary or '—'}</p>
<p>{record.follow_up_note or ''}</p>
{f'<h3>Gizli hekim notu</h3><p>{conf}</p>' if conf else ''}
<div class="sign">
<div>İşyeri Hekimi<br><b>{record.physician_name or '........................'}</b></div>
<div>İşveren / Vekili<br><b>........................</b></div>
</div>
<p style="margin-top:18px;font-size:12px;color:#64748b">Yazdır: Ctrl+P · İSG Suite OSGB</p>
</div></body></html>"""
    return HTMLResponse(html)


@router.post("/{record_id}/report", response_model=HealthRecordResponse)
async def upload_health_report(
    record_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*HEALTH_ROLES)),
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
                pass
            try:
                old.unlink()
            except OSError:
                pass
    rel = f"{record.company_id}/health/{record.id}_{uuid4().hex[:10]}{ext}"
    target = _upload_root() / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    record.report_file_name = name
    record.report_storage_path = rel.replace("\\", "/")
    record.report_content_type = file.content_type or {
        ".pdf": "application/pdf",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    }.get(ext, "application/octet-stream")
    db.commit()
    db.refresh(record)
    employee = db.get(Employee, record.employee_id)
    return _to_response(record, employee, user.role in PHYSICIAN_ROLES)


@router.get("/{record_id}/report")
def download_health_report(
    record_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*HEALTH_ROLES)),
):
    from fastapi.responses import FileResponse

    record = db.get(HealthRecord, record_id)
    if not record or record.deleted_at:
        raise HTTPException(404, "Sağlık kaydı bulunamadı.")
    ensure_access(db, user, record.company_id)
    if not record.report_storage_path:
        raise HTTPException(404, "Rapor dosyası yok.")
    path = (_upload_root() / record.report_storage_path).resolve()
    if _upload_root() not in path.parents or not path.exists():
        raise HTTPException(404, "Dosya bulunamadı.")
    return FileResponse(
        path,
        media_type=record.report_content_type or "application/octet-stream",
        filename=record.report_file_name or path.name,
    )
