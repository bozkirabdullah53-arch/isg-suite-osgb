"""Professional OHS committee API layered over the legacy compliance register.

The legacy tables and historical text snapshots remain intact. New writes use
stable identities and strict company/workplace validation.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.api.deps import require_roles
from app.core.database import get_db
from app.models.entities import Company, Employee, OhsCommitteeMeeting, User, UserRole
from app.services.assigned_team import assigned_team
from app.services.committee_meeting_pdf import build_committee_meeting_pdf

router = APIRouter(prefix="/ohs-committee", tags=["İSG Kurulu Pro"])
EDIT = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST)
VIEW = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST, UserRole.WORKPLACE_PHYSICIAN)
MANDATORY = {"isveren_vekili", "igu", "hekim"}
OFFICIAL_STATUSES = {"active", "completed", "approved", "awaiting_approval", "awaiting_signatures", "signed"}
ROLE_LABELS = {
    "isveren_vekili": "İşveren / İşveren Vekili",
    "igu": "İş Güvenliği Uzmanı",
    "hekim": "İşyeri Hekimi",
    "calisan_temsilcisi": "Çalışan Temsilcisi",
    "destek": "Destek Elemanı",
    "sekreter": "Kurul Sekreteri",
    "baskan": "Kurul Başkanı",
    "diger": "Diğer Üye",
}


class MemberSelection(BaseModel):
    company_id: int
    role_code: str = Field(min_length=2, max_length=40)
    source_type: str = Field(pattern="^(employee|professional|employer|user|manual)$")
    source_id: int | None = None
    full_name: str | None = Field(default=None, max_length=160)
    corporate_email: str | None = Field(default=None, max_length=255)
    committee_duty: str | None = Field(default=None, max_length=120)
    start_date: date | None = None
    notes: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_source(self):
        if self.source_type in {"employee", "professional", "user"} and not self.source_id:
            raise ValueError("Seçilen kişi için kaynak kimliği gereklidir.")
        if self.source_type == "manual" and not (self.full_name and self.corporate_email):
            raise ValueError("Manuel üye için ad soyad ve kurumsal e-posta zorunludur.")
        return self


class MeetingValidatedCreate(BaseModel):
    company_id: int
    meeting_date: date
    title: str | None = Field(default="İSG Kurulu Toplantısı", max_length=220)
    meeting_no: str | None = Field(default=None, max_length=60)
    document_no: str | None = Field(default=None, max_length=80)
    revision_no: str = Field(default="00", max_length=30)
    status: str = Field(default="draft", max_length=40)
    signature_status: str = Field(default="not_signed", max_length=40)
    start_time: str | None = Field(default=None, max_length=10)
    end_time: str | None = Field(default=None, max_length=10)
    location: str | None = Field(default=None, max_length=220)
    meeting_type: str | None = Field(default="Olağan", max_length=60)
    agenda: str | None = Field(default=None, max_length=4000)
    decisions: str | None = Field(default=None, max_length=4000)
    next_meeting_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


def _normalize(value: str | None) -> str:
    raw = unicodedata.normalize("NFKC", value or "").strip().casefold()
    return re.sub(r"\s+", " ", raw)


def _candidate_key(source_type: str, source_id: int | str, company_id: int) -> str:
    return f"{source_type}:{company_id}:{source_id}"


def _member_rows(db: Session, company_id: int) -> list[dict]:
    return list(db.execute(text("""
        SELECT id, company_id, role_code, full_name, start_date, end_date, notes,
               employee_id, user_id, branch_id, identity_key, source_type, source_ref,
               job_title_snapshot, professional_role_snapshot, email_snapshot,
               is_mandatory, is_active, created_at
        FROM ohs_committee_members
        WHERE company_id = :company_id AND is_active = true
        ORDER BY is_mandatory DESC, role_code, full_name, id
    """), {"company_id": company_id}).mappings())


def _missing_mandatory(db: Session, company_id: int) -> list[str]:
    roles = {r["role_code"] for r in _member_rows(db, company_id)}
    return [ROLE_LABELS[r] for r in ("isveren_vekili", "igu", "hekim") if r not in roles]


@router.get("/candidates")
def committee_candidates(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW)),
):
    ensure_company_access(db, user, company_id)
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "İşyeri bulunamadı.")

    existing = {r.get("identity_key") for r in _member_rows(db, company_id) if r.get("identity_key")}
    team = assigned_team(db, company_id)
    mandatory = []

    employer_name = (company.authorized_person or "").strip()
    if employer_name:
        key = _candidate_key("employer", company_id, company_id)
        mandatory.append({
            "identity_key": key,
            "source_type": "employer",
            "source_id": company_id,
            "full_name": employer_name,
            "job_title": "İşveren / İşveren Vekili",
            "professional_role": "İşveren",
            "suggested_role_code": "isveren_vekili",
            "mandatory": True,
            "assigned": True,
            "selected": key in existing,
            "company_id": company_id,
            "company_name": company.name,
        })
    else:
        mandatory.append({"missing": True, "suggested_role_code": "isveren_vekili", "mandatory": True, "message": "İşveren veya işveren vekili bilgisi bulunamadı."})

    for team_key, role_code, missing_message in (
        ("safety_specialist", "igu", "Bu işyerine iş güvenliği uzmanı atanmamış."),
        ("workplace_physician", "hekim", "Bu işyerine işyeri hekimi atanmamış."),
    ):
        person = team.get(team_key)
        if not person:
            mandatory.append({"missing": True, "suggested_role_code": role_code, "mandatory": True, "message": missing_message})
            continue
        key = _candidate_key("professional", person["professional_id"], company_id)
        mandatory.append({
            "identity_key": key,
            "source_type": "professional",
            "source_id": person["professional_id"],
            "source_ref": str(person.get("assignment_id") or ""),
            "full_name": person["full_name"],
            "job_title": person.get("title"),
            "professional_role": ROLE_LABELS[role_code],
            "suggested_role_code": role_code,
            "mandatory": True,
            "assigned": True,
            "selected": key in existing,
            "company_id": company_id,
            "company_name": company.name,
        })

    employees = list(db.scalars(select(Employee).where(Employee.company_id == company_id, Employee.is_active.is_(True)).order_by(Employee.full_name)).all())
    other = []
    for employee in employees:
        key = _candidate_key("employee", employee.id, company_id)
        other.append({
            "identity_key": key,
            "source_type": "employee",
            "source_id": employee.id,
            "full_name": employee.full_name,
            "job_title": employee.job_title,
            "department": employee.department,
            "branch_id": employee.branch_id,
            "suggested_role_code": "calisan_temsilcisi",
            "mandatory": False,
            "assigned": True,
            "selected": key in existing,
            "company_id": company_id,
            "company_name": company.name,
        })
    return {"company_id": company_id, "company_name": company.name, "mandatory": mandatory, "other": other, "selected_identity_keys": sorted(existing), "missing_mandatory": _missing_mandatory(db, company_id)}


@router.get("/members/detail")
def committee_members_detail(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW)),
):
    ensure_company_access(db, user, company_id)
    rows = _member_rows(db, company_id)
    for row in rows:
        row["role_label"] = ROLE_LABELS.get(row["role_code"], row["role_code"])
    return rows


@router.post("/members/validated", status_code=201)
def create_validated_member(
    payload: MemberSelection,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT)),
):
    ensure_company_access(db, user, payload.company_id)
    company = db.get(Company, payload.company_id)
    if not company:
        raise HTTPException(404, "İşyeri bulunamadı.")
    if payload.role_code not in ROLE_LABELS:
        raise HTTPException(422, "Geçersiz kurul görevi.")

    employee_id = user_id = branch_id = None
    source_ref = None
    job_title = professional_role = email = None
    is_mandatory = payload.role_code in MANDATORY

    if payload.source_type == "employee":
        employee = db.get(Employee, payload.source_id)
        if not employee or not employee.is_active:
            raise HTTPException(422, "Seçilen personel aktif değil veya bulunamadı.")
        if employee.company_id != payload.company_id:
            raise HTTPException(403, "Başka işyerine ait personel kurul üyesi yapılamaz.")
        identity_key = _candidate_key("employee", employee.id, payload.company_id)
        full_name, employee_id, branch_id = employee.full_name, employee.id, employee.branch_id
        job_title = employee.job_title
    elif payload.source_type == "professional":
        team = assigned_team(db, payload.company_id)
        matched = None
        for value in team.values():
            if value and int(value["professional_id"]) == int(payload.source_id):
                matched = value
                break
        if not matched:
            raise HTTPException(422, "Uzman/hekim bu işyerinde aktif görevlendirilmiş değil.")
        identity_key = _candidate_key("professional", matched["professional_id"], payload.company_id)
        full_name = matched["full_name"]
        job_title = matched.get("title")
        professional_role = ROLE_LABELS.get(payload.role_code)
        source_ref = str(matched.get("assignment_id") or "")
    elif payload.source_type == "employer":
        if not company.authorized_person:
            raise HTTPException(422, "İşveren veya işveren vekili bilgisi bulunamadı.")
        identity_key = _candidate_key("employer", company.id, company.id)
        full_name = company.authorized_person
        job_title = "İşveren / İşveren Vekili"
    elif payload.source_type == "user":
        selected_user = db.get(User, payload.source_id)
        if not selected_user or not selected_user.is_active:
            raise HTTPException(422, "Seçilen kullanıcı aktif değil veya bulunamadı.")
        if selected_user.company_id != payload.company_id:
            raise HTTPException(403, "Başka işyerine ait kullanıcı kurul üyesi yapılamaz.")
        identity_key = _candidate_key("user", selected_user.id, payload.company_id)
        full_name, user_id, email = selected_user.full_name, selected_user.id, selected_user.email
        professional_role = str(selected_user.role.value if hasattr(selected_user.role, "value") else selected_user.role)
    else:
        normalized_email = _normalize(payload.corporate_email)
        identity_key = f"manual:{payload.company_id}:{hashlib.sha256(normalized_email.encode()).hexdigest()[:24]}"
        full_name, email = payload.full_name.strip(), payload.corporate_email.strip().lower()

    duplicate = db.execute(text("SELECT id FROM ohs_committee_members WHERE company_id=:company_id AND is_active=true AND (identity_key=:identity_key OR (:employee_id IS NOT NULL AND employee_id=:employee_id) OR (:user_id IS NOT NULL AND user_id=:user_id)) LIMIT 1"), {"company_id": payload.company_id, "identity_key": identity_key, "employee_id": employee_id, "user_id": user_id}).scalar()
    if duplicate:
        raise HTTPException(409, "Bu kişi bu kurulda zaten üye olarak kayıtlıdır.")

    try:
        row = db.execute(text("""
            INSERT INTO ohs_committee_members
                (company_id, role_code, full_name, start_date, notes, is_active, created_by_id, created_at,
                 employee_id, user_id, branch_id, identity_key, source_type, source_ref,
                 job_title_snapshot, professional_role_snapshot, email_snapshot, is_mandatory)
            VALUES
                (:company_id, :role_code, :full_name, :start_date, :notes, true, :created_by_id, :created_at,
                 :employee_id, :user_id, :branch_id, :identity_key, :source_type, :source_ref,
                 :job_title, :professional_role, :email, :is_mandatory)
            RETURNING id
        """), {
            "company_id": payload.company_id, "role_code": payload.role_code, "full_name": full_name,
            "start_date": payload.start_date, "notes": payload.notes, "created_by_id": user.id,
            "created_at": datetime.utcnow(), "employee_id": employee_id, "user_id": user_id,
            "branch_id": branch_id, "identity_key": identity_key, "source_type": payload.source_type,
            "source_ref": source_ref, "job_title": job_title, "professional_role": professional_role,
            "email": email, "is_mandatory": is_mandatory,
        }).scalar_one()
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Bu kişi bu kurulda zaten üye olarak kayıtlıdır.") from exc
    return {"id": row, "identity_key": identity_key, "full_name": full_name, "role_code": payload.role_code, "role_label": ROLE_LABELS[payload.role_code], "is_mandatory": is_mandatory}


@router.post("/meetings/validated", status_code=201)
def create_validated_meeting(
    payload: MeetingValidatedCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT)),
):
    ensure_company_access(db, user, payload.company_id)
    missing = _missing_mandatory(db, payload.company_id)
    if payload.status.casefold() in OFFICIAL_STATUSES and missing:
        raise HTTPException(409, f"Kurul eksik. Zorunlu üyeler: {', '.join(missing)}")
    members = _member_rows(db, payload.company_id)
    snapshot = [{
        "member_id": m["id"], "identity_key": m.get("identity_key"), "full_name": m["full_name"],
        "role_code": m["role_code"], "role_label": ROLE_LABELS.get(m["role_code"], m["role_code"]),
        "job_title": m.get("job_title_snapshot"), "professional_role": m.get("professional_role_snapshot"),
        "attendance_status": "Belirtilmedi", "signature_status": "İmzalanmadı",
    } for m in members]
    row_id = db.execute(text("""
        INSERT INTO ohs_committee_meetings
            (company_id, meeting_date, agenda, decisions, attendees, next_meeting_date, notes, is_active,
             created_by_id, created_at, title, meeting_no, document_no, revision_no, status,
             signature_status, start_time, end_time, location, meeting_type, member_snapshot_json)
        VALUES
            (:company_id, :meeting_date, :agenda, :decisions, :attendees, :next_meeting_date, :notes, true,
             :created_by_id, :created_at, :title, :meeting_no, :document_no, :revision_no, :status,
             :signature_status, :start_time, :end_time, :location, :meeting_type, :snapshot)
        RETURNING id
    """), {**payload.model_dump(), "attendees": ", ".join(m["full_name"] for m in members), "created_by_id": user.id, "created_at": datetime.utcnow(), "snapshot": json.dumps(snapshot, ensure_ascii=False)}).scalar_one()
    db.commit()
    return {"id": row_id, "status": payload.status, "member_count": len(snapshot), "missing_mandatory": missing}


@router.get("/meetings/{meeting_id}/pdf")
def committee_meeting_pdf(
    meeting_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW)),
):
    meeting = db.execute(text("SELECT * FROM ohs_committee_meetings WHERE id=:id AND is_active=true"), {"id": meeting_id}).mappings().first()
    if not meeting:
        raise HTTPException(404, "Toplantı bulunamadı.")
    ensure_company_access(db, user, meeting["company_id"])
    company = db.get(Company, meeting["company_id"])
    snapshot_raw = meeting.get("member_snapshot_json")
    if snapshot_raw:
        try:
            members = json.loads(snapshot_raw)
        except json.JSONDecodeError:
            members = []
    else:
        members = [{
            "identity_key": m.get("identity_key"), "full_name": m["full_name"], "role_code": m["role_code"],
            "role_label": ROLE_LABELS.get(m["role_code"], m["role_code"]), "job_title": m.get("job_title_snapshot"),
            "professional_role": m.get("professional_role_snapshot"), "attendance_status": "Belirtilmedi",
            "signature_status": "İmzalanmadı",
        } for m in _member_rows(db, meeting["company_id"])]
    pdf = build_committee_meeting_pdf(company={"name": company.name if company else "—", "address": getattr(company, "address", None)}, meeting=dict(meeting), members=members)
    digest = hashlib.sha256(pdf).hexdigest()
    db.execute(text("UPDATE ohs_committee_meetings SET pdf_sha256=:digest, pdf_generated_at=:generated WHERE id=:id"), {"digest": digest, "generated": datetime.utcnow(), "id": meeting_id})
    db.commit()
    safe_company = re.sub(r"[^A-Za-z0-9_-]+", "_", (company.name if company else "Isyeri"))[:60]
    safe_no = re.sub(r"[^A-Za-z0-9_-]+", "_", str(meeting.get("meeting_no") or meeting_id))[:30]
    meeting_date = meeting.get("meeting_date")
    stamp = meeting_date.isoformat() if hasattr(meeting_date, "isoformat") else str(meeting_date)
    filename = f"OHS_Committee_Meeting_{safe_company}_{safe_no}_{stamp}.pdf"
    return StreamingResponse(BytesIO(pdf), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{filename}"', "X-Document-SHA256": digest})
