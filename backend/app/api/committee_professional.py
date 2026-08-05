"""Professional OHS committee API with integrity, approval, signatures and history."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import date, datetime
from io import BytesIO

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.api.deps import require_roles
from app.core.database import get_db
from app.models.entities import Company, Employee, EyasStep, User, UserRole
from app.services.assigned_team import assigned_team
from app.services.committee_meeting_pdf import build_committee_meeting_pdf
from app.services.committee_signature import (
    artifact_bytes_by_id,
    create_signature_request,
    final_signed_bytes,
    signature_source,
)
from app.services.committee_workflow import (
    approval_members_for_pdf,
    assert_can_manage,
    can_manage_company,
    invalidate_approval_for_material_change,
    remove_member,
    snapshot_members,
    submit_for_approval,
    work_queue,
    work_queue_item,
)

router = APIRouter(prefix="/ohs-committee", tags=["İSG Kurulu Pro"])
EDIT = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST)
MANAGE = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST, UserRole.COMPANY_ADMIN)
VIEW = (
    UserRole.GLOBAL_ADMIN,
    UserRole.SAFETY_SPECIALIST,
    UserRole.WORKPLACE_PHYSICIAN,
    UserRole.COMPANY_ADMIN,
)
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
MATERIAL_FIELDS = {
    "meeting_date", "title", "meeting_no", "document_no", "revision_no",
    "start_time", "end_time", "location", "meeting_type", "agenda", "decisions",
    "next_meeting_date", "notes",
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


class MemberRemovalBody(BaseModel):
    reason_code: str = Field(min_length=3, max_length=60)
    reason_text: str | None = Field(default=None, max_length=1000)


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


class MeetingUpdate(BaseModel):
    meeting_date: date | None = None
    title: str | None = Field(default=None, max_length=220)
    meeting_no: str | None = Field(default=None, max_length=60)
    document_no: str | None = Field(default=None, max_length=80)
    revision_no: str | None = Field(default=None, max_length=30)
    status: str | None = Field(default=None, max_length=40)
    start_time: str | None = Field(default=None, max_length=10)
    end_time: str | None = Field(default=None, max_length=10)
    location: str | None = Field(default=None, max_length=220)
    meeting_type: str | None = Field(default=None, max_length=60)
    agenda: str | None = Field(default=None, max_length=4000)
    decisions: str | None = Field(default=None, max_length=4000)
    next_meeting_date: date | None = None
    notes: str | None = Field(default=None, max_length=2000)


def _client_ip(request: Request) -> str | None:
    forwarded = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()[:64]
    return request.client.host[:64] if request.client and request.client.host else None


def _normalize(value: str | None) -> str:
    raw = unicodedata.normalize("NFKC", value or "").strip().casefold()
    return re.sub(r"\s+", " ", raw)


def _candidate_key(source_type: str, source_id: int | str, company_id: int) -> str:
    return f"{source_type}:{company_id}:{source_id}"


def _member_rows(db: Session, company_id: int) -> list[dict]:
    rows = db.execute(text("""
        SELECT id, company_id, role_code, full_name, start_date, end_date, notes,
               employee_id, user_id, branch_id, identity_key, source_type, source_ref,
               job_title_snapshot, professional_role_snapshot, email_snapshot,
               is_mandatory, is_active, created_at,
               removed_at, removed_by_id, removal_reason_code, removal_reason_text
        FROM ohs_committee_members
        WHERE company_id=:company_id AND is_active=true
        ORDER BY is_mandatory DESC, role_code, full_name, id
    """), {"company_id": company_id}).mappings()
    return [dict(row) for row in rows]


def _find_duplicate_member_id(
    db: Session,
    *,
    company_id: int,
    identity_key: str,
    employee_id: int | None,
    user_id: int | None,
) -> int | None:
    predicates = ["identity_key=:identity_key"]
    params: dict[str, int | str] = {"company_id": company_id, "identity_key": identity_key}
    if employee_id is not None:
        predicates.append("employee_id=:employee_id")
        params["employee_id"] = employee_id
    if user_id is not None:
        predicates.append("user_id=:user_id")
        params["user_id"] = user_id
    return db.execute(
        text(f"""
            SELECT id FROM ohs_committee_members
             WHERE company_id=:company_id AND is_active=true
               AND ({' OR '.join(predicates)}) LIMIT 1
        """),
        params,
    ).scalar()


def _missing_mandatory(db: Session, company_id: int) -> list[str]:
    roles = {row["role_code"] for row in _member_rows(db, company_id)}
    return [ROLE_LABELS[code] for code in ("isveren_vekili", "igu", "hekim") if code not in roles]


def _meeting_row(db: Session, meeting_id: int) -> dict:
    row = db.execute(
        text("SELECT * FROM ohs_committee_meetings WHERE id=:id AND is_active=true"),
        {"id": meeting_id},
    ).mappings().first()
    if not row:
        raise HTTPException(404, "Toplantı bulunamadı.")
    return dict(row)


def _initials(name: str | None) -> str:
    return "".join(part[:1] for part in (name or "?").split()[:2]).upper()


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
    existing = {row.get("identity_key") for row in _member_rows(db, company_id) if row.get("identity_key")}
    team = assigned_team(db, company_id)
    mandatory = []
    employer_name = (company.authorized_person or "").strip()
    if employer_name:
        key = _candidate_key("employer", company_id, company_id)
        mandatory.append({
            "identity_key": key, "source_type": "employer", "source_id": company_id,
            "full_name": employer_name, "initials": _initials(employer_name),
            "job_title": "İşveren / İşveren Vekili", "professional_role": "İşveren",
            "suggested_role_code": "isveren_vekili", "mandatory": True,
            "assigned": True, "selected": key in existing, "company_id": company_id,
            "company_name": company.name,
        })
    else:
        mandatory.append({
            "missing": True, "suggested_role_code": "isveren_vekili", "mandatory": True,
            "message": "İşveren veya işveren vekili bilgisi bulunamadı.",
        })
    for team_key, role_code, missing_message in (
        ("safety_specialist", "igu", "Bu işyerine iş güvenliği uzmanı atanmamış."),
        ("workplace_physician", "hekim", "Bu işyerine işyeri hekimi atanmamış."),
    ):
        person = team.get(team_key)
        if not person:
            mandatory.append({
                "missing": True, "suggested_role_code": role_code,
                "mandatory": True, "message": missing_message,
            })
            continue
        key = _candidate_key("professional", person["professional_id"], company_id)
        mandatory.append({
            "identity_key": key, "source_type": "professional",
            "source_id": person["professional_id"],
            "source_ref": str(person.get("assignment_id") or ""),
            "full_name": person["full_name"], "initials": _initials(person["full_name"]),
            "job_title": person.get("title"), "professional_role": ROLE_LABELS[role_code],
            "suggested_role_code": role_code, "mandatory": True, "assigned": True,
            "selected": key in existing, "company_id": company_id, "company_name": company.name,
        })
    employees = list(
        db.scalars(
            select(Employee)
            .where(Employee.company_id == company_id, Employee.is_active.is_(True))
            .order_by(Employee.full_name)
        ).all()
    )
    other = []
    for employee in employees:
        key = _candidate_key("employee", employee.id, company_id)
        other.append({
            "identity_key": key, "source_type": "employee", "source_id": employee.id,
            "full_name": employee.full_name, "initials": _initials(employee.full_name),
            "job_title": employee.job_title, "department": employee.department,
            "branch_id": employee.branch_id, "suggested_role_code": "calisan_temsilcisi",
            "mandatory": False, "assigned": True, "selected": key in existing,
            "company_id": company_id, "company_name": company.name,
        })
    return {
        "company_id": company_id, "company_name": company.name, "mandatory": mandatory,
        "other": other, "selected_identity_keys": sorted(existing),
        "missing_mandatory": _missing_mandatory(db, company_id),
    }


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
        row["initials"] = _initials(row.get("full_name"))
    return rows


@router.post("/members/validated", status_code=201)
def create_validated_member(
    payload: MemberSelection,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE)),
):
    assert_can_manage(db, user, payload.company_id)
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
        matched = next(
            (value for value in team.values() if value and int(value["professional_id"]) == int(payload.source_id)),
            None,
        )
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
    duplicate = _find_duplicate_member_id(
        db,
        company_id=payload.company_id,
        identity_key=identity_key,
        employee_id=employee_id,
        user_id=user_id,
    )
    if duplicate:
        raise HTTPException(409, "Bu kişi bu kurulda zaten üye olarak kayıtlıdır.")
    try:
        row_id = db.execute(text("""
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
            "company_id": payload.company_id, "role_code": payload.role_code,
            "full_name": full_name, "start_date": payload.start_date, "notes": payload.notes,
            "created_by_id": user.id, "created_at": datetime.utcnow(),
            "employee_id": employee_id, "user_id": user_id, "branch_id": branch_id,
            "identity_key": identity_key, "source_type": payload.source_type,
            "source_ref": source_ref, "job_title": job_title,
            "professional_role": professional_role, "email": email,
            "is_mandatory": is_mandatory,
        }).scalar_one()
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Bu kişi bu kurulda zaten üye olarak kayıtlıdır.") from exc
    return {
        "id": row_id, "identity_key": identity_key, "full_name": full_name,
        "role_code": payload.role_code, "role_label": ROLE_LABELS[payload.role_code],
        "is_mandatory": is_mandatory,
    }


@router.post("/members/{member_id}/remove")
def remove_committee_member(
    member_id: int,
    payload: MemberRemovalBody,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE)),
):
    return remove_member(
        db,
        member_id=member_id,
        user=user,
        reason_code=payload.reason_code,
        reason_text=payload.reason_text,
        ip=_client_ip(request),
    )


@router.delete("/members/{member_id}")
def remove_committee_member_compat(
    member_id: int,
    request: Request,
    reason_code: str = Query("incorrectly_added"),
    reason_text: str | None = Query(None, max_length=1000),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE)),
):
    return remove_member(
        db,
        member_id=member_id,
        user=user,
        reason_code=reason_code,
        reason_text=reason_text,
        ip=_client_ip(request),
    )


@router.post("/meetings/validated", status_code=201)
def create_validated_meeting(
    payload: MeetingValidatedCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT)),
):
    assert_can_manage(db, user, payload.company_id)
    missing = _missing_mandatory(db, payload.company_id)
    if payload.status.casefold() in OFFICIAL_STATUSES and missing:
        raise HTTPException(409, f"Kurul eksik. Zorunlu üyeler: {', '.join(missing)}")
    members = _member_rows(db, payload.company_id)
    snapshot = [{
        "member_id": member["id"], "identity_key": member.get("identity_key"),
        "full_name": member["full_name"], "role_code": member["role_code"],
        "role_label": ROLE_LABELS.get(member["role_code"], member["role_code"]),
        "job_title": member.get("job_title_snapshot"),
        "professional_role": member.get("professional_role_snapshot"),
        "attendance_status": "Belirtilmedi", "signature_status": "İmzalanmadı",
    } for member in members]
    now = datetime.utcnow()
    row_id = db.execute(text("""
        INSERT INTO ohs_committee_meetings
            (company_id, meeting_date, agenda, decisions, attendees, next_meeting_date, notes, is_active,
             created_by_id, created_at, title, meeting_no, document_no, revision_no, status,
             signature_status, start_time, end_time, location, meeting_type, member_snapshot_json,
             approval_status, document_version, updated_at)
        VALUES
            (:company_id, :meeting_date, :agenda, :decisions, :attendees, :next_meeting_date, :notes, true,
             :created_by_id, :created_at, :title, :meeting_no, :document_no, :revision_no, :status,
             :signature_status, :start_time, :end_time, :location, :meeting_type, :snapshot,
             :approval_status, 1, :created_at)
        RETURNING id
    """), {
        **payload.model_dump(), "attendees": ", ".join(member["full_name"] for member in members),
        "created_by_id": user.id, "created_at": now,
        "snapshot": json.dumps(snapshot, ensure_ascii=False),
        "approval_status": "incomplete" if missing else "draft",
    }).scalar_one()
    db.commit()
    return {
        "id": row_id, "status": payload.status,
        "approval_status": "incomplete" if missing else "draft",
        "member_count": len(snapshot), "missing_mandatory": missing,
    }


@router.get("/work-queue")
def committee_work_queue(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW)),
):
    return work_queue(db, user)


@router.get("/meetings/{meeting_id}/detail")
def committee_meeting_detail(
    meeting_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW)),
):
    return work_queue_item(db, meeting_id, user=user)


@router.post("/meetings/{meeting_id}/submit-approval")
def submit_committee_meeting(
    meeting_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE)),
):
    return submit_for_approval(
        db,
        meeting_id=meeting_id,
        user=user,
        ip=_client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:500] or None,
    )


@router.post("/meetings/{meeting_id}/signature-request")
def request_committee_signature(
    meeting_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW)),
):
    return create_signature_request(
        db, meeting_id=meeting_id, user=user, ip=_client_ip(request)
    )


@router.get("/meetings/{meeting_id}/signature-source")
def download_committee_signature_source(
    meeting_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW)),
):
    raw, filename = signature_source(db, meeting_id, user)
    return StreamingResponse(
        BytesIO(raw),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/meetings/{meeting_id}")
def update_committee_meeting(
    meeting_id: int,
    payload: MeetingUpdate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*MANAGE)),
):
    meeting = _meeting_row(db, meeting_id)
    assert_can_manage(db, user, meeting["company_id"])
    data = payload.model_dump(exclude_unset=True)
    if not data:
        return work_queue_item(db, meeting_id, user=user)
    target_status = str(data.get("status") or meeting.get("status") or "draft").casefold()
    if target_status in OFFICIAL_STATUSES:
        missing = _missing_mandatory(db, meeting["company_id"])
        if missing:
            raise HTTPException(409, f"Kurul eksik. Zorunlu üyeler: {', '.join(missing)}")
    changed_material = [
        key for key in MATERIAL_FIELDS
        if key in data and data[key] != meeting.get(key)
    ]
    if changed_material and meeting.get("approval_workflow_id"):
        invalidate_approval_for_material_change(
            db,
            meeting_id=meeting_id,
            user=user,
            changed_fields=changed_material,
            ip=_client_ip(request),
        )
    allowed = set(MeetingUpdate.model_fields)
    assignments = []
    params: dict[str, object] = {"id": meeting_id, "updated_at": datetime.utcnow()}
    for key, value in data.items():
        if key in allowed:
            assignments.append(f"{key}=:{key}")
            params[key] = value
    if assignments:
        assignments.append("updated_at=:updated_at")
        db.execute(
            text(f"UPDATE ohs_committee_meetings SET {', '.join(assignments)} WHERE id=:id"),
            params,
        )
        db.commit()
    return work_queue_item(db, meeting_id, user=user)


def _authorize_version(db: Session, user: User, version_row: dict) -> None:
    ensure_company_access(db, user, version_row["company_id"])
    if can_manage_company(db, user, version_row["company_id"]):
        return
    workflow_id = version_row.get("approval_workflow_id")
    if workflow_id and db.scalar(
        select(EyasStep.id).where(
            EyasStep.workflow_id == workflow_id,
            EyasStep.assignee_user_id == user.id,
        ).limit(1)
    ):
        return
    signed = db.scalar(text("""
        SELECT id FROM ohs_committee_signature_steps
         WHERE meeting_id=:meeting_id AND document_version=:version
           AND signer_user_id=:user_id LIMIT 1
    """), {
        "meeting_id": version_row["meeting_id"],
        "version": version_row["document_version"],
        "user_id": user.id,
    })
    if not signed:
        raise HTTPException(403, "Bu tarihsel toplantı sürümüne erişim yetkiniz yok.")


@router.get("/meetings/{meeting_id}/versions")
def list_committee_meeting_versions(
    meeting_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW)),
):
    meeting = _meeting_row(db, meeting_id)
    work_queue_item(db, meeting_id, user=user)
    rows = db.execute(text("""
        SELECT id, meeting_id, company_id, document_version,
               approval_workflow_id, final_signature_artifact_id,
               pdf_sha256, archive_reason, created_at
          FROM ohs_committee_meeting_versions
         WHERE meeting_id=:meeting_id
         ORDER BY document_version DESC
    """), {"meeting_id": meeting["id"]}).mappings().all()
    return [dict(row) for row in rows]


@router.get("/meetings/{meeting_id}/versions/{document_version}/pdf")
def historical_committee_meeting_pdf(
    meeting_id: int,
    document_version: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW)),
):
    row = db.execute(text("""
        SELECT * FROM ohs_committee_meeting_versions
         WHERE meeting_id=:meeting_id AND document_version=:version
    """), {"meeting_id": meeting_id, "version": document_version}).mappings().first()
    if not row:
        raise HTTPException(404, "Tarihsel toplantı sürümü bulunamadı.")
    version_row = dict(row)
    _authorize_version(db, user, version_row)
    if version_row.get("final_signature_artifact_id"):
        signed = artifact_bytes_by_id(db, int(version_row["final_signature_artifact_id"]))
        if signed:
            return StreamingResponse(
                BytesIO(signed), media_type="application/pdf",
                headers={"Content-Disposition": f'attachment; filename="OHS_Committee_Meeting_{meeting_id}_v{document_version}_signed.pdf"'},
            )
    try:
        meeting = json.loads(version_row["meeting_snapshot_json"])
        members = json.loads(version_row.get("member_snapshot_json") or "[]")
    except (TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(409, "Tarihsel toplantı snapshotı okunamadı.") from exc
    members = approval_members_for_pdf(db, meeting, members)
    company = db.get(Company, version_row["company_id"])
    pdf = build_committee_meeting_pdf(
        company={"name": company.name if company else "—", "address": getattr(company, "address", None)},
        meeting=meeting,
        members=members,
    )
    return StreamingResponse(
        BytesIO(pdf), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="OHS_Committee_Meeting_{meeting_id}_v{document_version}.pdf"'},
    )


@router.get("/meetings/{meeting_id}/pdf")
def committee_meeting_pdf(
    meeting_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW)),
):
    meeting = _meeting_row(db, meeting_id)
    work_queue_item(db, meeting_id, user=user)
    version = int(meeting.get("document_version") or 1)
    signed = final_signed_bytes(db, meeting_id, version)
    if signed:
        digest = hashlib.sha256(signed).hexdigest()
        return StreamingResponse(
            BytesIO(signed), media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="OHS_Committee_Meeting_{meeting_id}_v{version}_signed.pdf"',
                "X-Document-SHA256": digest,
            },
        )
    company = db.get(Company, meeting["company_id"])
    members = approval_members_for_pdf(db, meeting, snapshot_members(meeting))
    pdf = build_committee_meeting_pdf(
        company={"name": company.name if company else "—", "address": getattr(company, "address", None)},
        meeting=meeting,
        members=members,
    )
    digest = hashlib.sha256(pdf).hexdigest()
    db.execute(
        text("UPDATE ohs_committee_meetings SET pdf_sha256=:digest, pdf_generated_at=:generated WHERE id=:id"),
        {"digest": digest, "generated": datetime.utcnow(), "id": meeting_id},
    )
    db.commit()
    safe_company = re.sub(r"[^A-Za-z0-9_-]+", "_", (company.name if company else "Isyeri"))[:60]
    safe_no = re.sub(r"[^A-Za-z0-9_-]+", "_", str(meeting.get("meeting_no") or meeting_id))[:30]
    meeting_date = meeting.get("meeting_date")
    stamp = meeting_date.isoformat() if hasattr(meeting_date, "isoformat") else str(meeting_date)
    filename = f"OHS_Committee_Meeting_{safe_company}_{safe_no}_{stamp}_v{version}.pdf"
    return StreamingResponse(
        BytesIO(pdf), media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "X-Document-SHA256": digest},
    )
