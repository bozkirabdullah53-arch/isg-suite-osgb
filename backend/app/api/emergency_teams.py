"""0.9.134 — Acil durum ekipleri / destek elemanları API (İSG uzmanı).

Mevcut modüllere dokunmaz; yalnızca yeni tablolarla çalışır. Tenant izolasyonu
company_ids_for_query / ensure_company_access üzerinden yapılır. Silme yumuşaktır
(is_active=False). İşyeri hekimi salt-okunur (VIEW), düzenleme yalnızca global
yönetici ve İSG uzmanına açıktır.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.api.company_access import company_ids_for_query, ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.config import settings
from app.core.database import get_db
from app.models.entities import (
    Company,
    Employee,
    EmergencyTeam,
    EmergencyTeamAssignment,
    EmergencyTeamTraining,
    EmergencyTeamType,
    IsgProfessional,
    User,
    UserRole,
    WorkplaceAssignment,
)
from app.schemas.emergency_teams import (
    DEFAULT_TEAM_TYPES,
    AssignmentCreate,
    AssignmentResponse,
    AssignmentUpdate,
    TeamCreate,
    TeamResponse,
    TeamStatus,
    TeamTypeResponse,
    TeamUpdate,
    TrainingCreate,
    TrainingResponse,
)
from app.services.emergency_team_logic import (
    assignment_warnings,
    cert_status_from_trainings,
    employee_active_team_counts,
    ensure_default_teams,
    ensure_system_team_types,
    team_status,
    team_warnings,
)
from app.services.emergency_team_reports import (
    build_assignment_letter_pdf,
    build_teams_excel,
    build_teams_pdf,
)

router = APIRouter(prefix="/emergency-teams", tags=["Acil Durum Ekipleri"])

EDIT_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST)
VIEW_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST, UserRole.WORKPLACE_PHYSICIAN)
ALLOWED_CERT = {".jpg", ".jpeg", ".png", ".pdf"}
ENGINE = "emergency-teams-v1"


def _upload_root() -> Path:
    root = Path(settings.upload_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


# --------------------------------------------------------------------------- #
# Loaders
# --------------------------------------------------------------------------- #
def _load_team(db: Session, team_id: int) -> EmergencyTeam:
    row = db.scalar(
        select(EmergencyTeam)
        .where(EmergencyTeam.id == team_id)
        .options(
            selectinload(EmergencyTeam.team_type),
            selectinload(EmergencyTeam.assignments).selectinload(EmergencyTeamAssignment.trainings),
            selectinload(EmergencyTeam.assignments).selectinload(EmergencyTeamAssignment.employee),
        )
    )
    if not row or not row.is_active:
        raise HTTPException(404, "Ekip bulunamadı.")
    return row


def _load_assignment(db: Session, assignment_id: int) -> EmergencyTeamAssignment:
    row = db.scalar(
        select(EmergencyTeamAssignment)
        .where(EmergencyTeamAssignment.id == assignment_id)
        .options(
            selectinload(EmergencyTeamAssignment.trainings),
            selectinload(EmergencyTeamAssignment.employee),
            selectinload(EmergencyTeamAssignment.team),
        )
    )
    if not row or not row.is_active:
        raise HTTPException(404, "Görevlendirme bulunamadı.")
    return row


# --------------------------------------------------------------------------- #
# Response builders
# --------------------------------------------------------------------------- #
def _assignment_response(
    row: EmergencyTeamAssignment,
    *,
    workload: dict[int, int] | None = None,
) -> AssignmentResponse:
    cert, vu = cert_status_from_trainings(list(row.trainings or []))
    active_team_count = (workload or {}).get(row.employee_id, 1)
    warnings = assignment_warnings(cert_state=cert, active_team_count=active_team_count)
    return AssignmentResponse(
        id=row.id,
        company_id=row.company_id,
        team_id=row.team_id,
        team_name=getattr(row.team, "name", None),
        employee_id=row.employee_id,
        employee_name=getattr(row.employee, "full_name", None),
        membership=row.membership,
        is_leader=bool(row.is_leader),
        role_title=row.role_title,
        shift=row.shift,
        phone=row.phone,
        email=row.email,
        section=row.section,
        personnel_no=row.personnel_no,
        assign_start=row.assign_start,
        assign_end=row.assign_end,
        letter_date=row.letter_date,
        letter_no=row.letter_no,
        assigned_by=row.assigned_by,
        notes=row.notes,
        cert_status=cert,
        cert_valid_until=vu,
        training_count=len(row.trainings or []),
        warnings=warnings,
        is_active=bool(row.is_active),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _team_response(
    team: EmergencyTeam,
    *,
    workload: dict[int, int] | None = None,
) -> TeamResponse:
    members = [a for a in (team.assignments or []) if a.is_active]
    asil = [a for a in members if a.membership == "asil"]
    yedek = [a for a in members if a.membership == "yedek"]
    cert_counts = {"green": 0, "yellow": 0, "red": 0, "grey": 0}
    leader_name = None
    for a in members:
        cert, _ = cert_status_from_trainings(list(a.trainings or []))
        cert_counts[cert] = cert_counts.get(cert, 0) + 1
        if a.id == team.leader_assignment_id or a.is_leader:
            leader_name = getattr(a.employee, "full_name", None) or leader_name
    has_leader = any(a.is_leader for a in members) or team.leader_assignment_id is not None

    status_dict = team_status(len(members), team.min_members)
    # Belge sorunları ekip durumunu "güncelleme gerekli" olarak işaretleyebilir
    if status_dict["code"] == "tam" and (cert_counts.get("red") or cert_counts.get("grey")):
        status_dict = {"code": "guncelleme", "label": "Güncelleme Gerekli", "tone": "warn"}

    warnings = team_warnings(
        team=team,
        active_members=len(members),
        asil_members=len(asil),
        has_leader=has_leader,
        cert_counts=cert_counts,
    )

    return TeamResponse(
        id=team.id,
        company_id=team.company_id,
        type_id=team.type_id,
        type_code=getattr(team.team_type, "code", None),
        type_name=getattr(team.team_type, "name", None),
        name=team.name,
        min_members=team.min_members,
        notes=team.notes,
        leader_assignment_id=team.leader_assignment_id,
        leader_name=leader_name,
        member_count=len(members),
        asil_count=len(asil),
        yedek_count=len(yedek),
        cert_summary=cert_counts,
        status=TeamStatus(**status_dict),
        warnings=warnings,
        is_active=bool(team.is_active),
        created_at=team.created_at,
        updated_at=team.updated_at,
    )


def _teams_for_company(db: Session, company_id: int) -> list[EmergencyTeam]:
    return list(
        db.scalars(
            select(EmergencyTeam)
            .where(EmergencyTeam.company_id == company_id, EmergencyTeam.is_active.is_(True))
            .options(
                selectinload(EmergencyTeam.team_type),
                selectinload(EmergencyTeam.assignments).selectinload(EmergencyTeamAssignment.trainings),
                selectinload(EmergencyTeam.assignments).selectinload(EmergencyTeamAssignment.employee),
            )
            .order_by(EmergencyTeam.id)
        ).all()
    )


def _specialist_name(db: Session, user: User, company_id: int) -> str | None:
    """Firmaya atanmış uzman adı; yoksa mevcut kullanıcı adı."""
    pro = db.scalar(
        select(IsgProfessional)
        .join(WorkplaceAssignment, WorkplaceAssignment.professional_id == IsgProfessional.id)
        .where(
            WorkplaceAssignment.company_id == company_id,
            IsgProfessional.is_active.is_(True),
        )
        .order_by(IsgProfessional.id)
        .limit(1)
    )
    if pro:
        return pro.full_name
    return getattr(user, "full_name", None)


# --------------------------------------------------------------------------- #
# Meta
# --------------------------------------------------------------------------- #
@router.get("/meta")
def meta(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    types = ensure_system_team_types(db)
    return {
        "engine": ENGINE,
        "memberships": ["asil", "yedek"],
        "cert_statuses": {
            "green": "Geçerli",
            "yellow": "30 gün içinde",
            "red": "Süresi dolmuş",
            "grey": "Kayıt yok",
        },
        "default_team_types": [{"code": c, "name": n} for c, n in DEFAULT_TEAM_TYPES],
        "team_types": [TeamTypeResponse.model_validate(t) for t in types],
        "note": "Yol gösterici hatırlatmalar sunar; kesin hukuki değerlendirme yerine geçmez.",
    }


# --------------------------------------------------------------------------- #
# Overview
# --------------------------------------------------------------------------- #
@router.get("/overview")
def overview(
    company_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    company_id = ensure_company_access(db, user, company_id)
    company = db.get(Company, company_id)
    if not company:
        raise HTTPException(404, "Firma bulunamadı.")

    ensure_system_team_types(db)
    # Salt-okunur roller otomatik oluşturma tetiklemez
    if user.role in EDIT_ROLES:
        ensure_default_teams(db, company_id, user.id)

    teams = _teams_for_company(db, company_id)
    workload = employee_active_team_counts(db, company_id)

    employee_count = db.scalar(
        select(func.count())
        .select_from(Employee)
        .where(Employee.company_id == company_id, Employee.is_active.is_(True))
    ) or 0

    team_payload = [_team_response(t, workload=workload) for t in teams]
    total_members = sum(t.member_count for t in team_payload)
    total_leaders = sum(1 for t in teams for a in (t.assignments or []) if a.is_active and a.is_leader)
    cert_red = sum(t.cert_summary.get("red", 0) for t in team_payload)
    cert_yellow = sum(t.cert_summary.get("yellow", 0) for t in team_payload)
    teams_ok = sum(1 for t in team_payload if t.status and t.status.code == "tam")
    teams_critical = sum(1 for t in team_payload if t.status and t.status.code == "kritik")

    warnings: list[str] = []
    for t in team_payload:
        for w in t.warnings:
            warnings.append(f"{t.name}: {w}")
    over_workers = [emp for emp, cnt in workload.items() if cnt >= 3]
    if over_workers:
        warnings.append(
            f"{len(over_workers)} personel 3+ aktif ekipte görünüyor — "
            "iş yükü dağılımının kontrol edilmesi önerilir."
        )

    return {
        "company": {
            "id": company.id,
            "name": company.name,
            "sgk_registry_no": company.sgk_registry_no,
            "address": company.address,
            "hazard_class": company.hazard_class,
        },
        "specialist_name": _specialist_name(db, user, company_id),
        "employee_count": int(employee_count),
        "kpis": {
            "team_count": len(team_payload),
            "member_count": total_members,
            "leader_count": total_leaders,
            "teams_ok": teams_ok,
            "teams_critical": teams_critical,
            "cert_expired": cert_red,
            "cert_soon": cert_yellow,
        },
        "warnings": warnings,
        "teams": team_payload,
        "can_edit": user.role in EDIT_ROLES,
    }


# --------------------------------------------------------------------------- #
# Teams CRUD
# --------------------------------------------------------------------------- #
@router.get("/teams", response_model=list[TeamResponse])
def list_teams(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    company_ids = company_ids_for_query(db, user, company_id)
    if company_ids == []:
        return []
    stmt = (
        select(EmergencyTeam)
        .where(EmergencyTeam.is_active.is_(True))
        .options(
            selectinload(EmergencyTeam.team_type),
            selectinload(EmergencyTeam.assignments).selectinload(EmergencyTeamAssignment.trainings),
            selectinload(EmergencyTeam.assignments).selectinload(EmergencyTeamAssignment.employee),
        )
        .order_by(EmergencyTeam.company_id, EmergencyTeam.id)
    )
    if company_ids is not None:
        stmt = stmt.where(EmergencyTeam.company_id.in_(company_ids))
    teams = list(db.scalars(stmt).all())
    workload_cache: dict[int, dict[int, int]] = {}
    out: list[TeamResponse] = []
    for t in teams:
        if t.company_id not in workload_cache:
            workload_cache[t.company_id] = employee_active_team_counts(db, t.company_id)
        out.append(_team_response(t, workload=workload_cache[t.company_id]))
    return out


@router.post("/teams", response_model=TeamResponse)
def create_team(
    payload: TeamCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    ensure_company_access(db, user, payload.company_id)
    ttype = db.get(EmergencyTeamType, payload.type_id)
    if not ttype or not ttype.is_active:
        raise HTTPException(422, "Geçersiz ekip türü.")
    if ttype.company_id is not None and ttype.company_id != payload.company_id:
        raise HTTPException(403, "Bu ekip türü başka firmaya ait.")
    min_members = payload.min_members if payload.min_members is not None else (ttype.min_members or 2)
    row = EmergencyTeam(
        company_id=payload.company_id,
        type_id=ttype.id,
        name=payload.name,
        min_members=min_members,
        notes=payload.notes,
        created_by_id=user.id,
    )
    db.add(row)
    db.commit()
    return _team_response(_load_team(db, row.id))


@router.put("/teams/{team_id}", response_model=TeamResponse)
def update_team(
    team_id: int,
    payload: TeamUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load_team(db, team_id)
    ensure_company_access(db, user, row.company_id)
    if payload.name is not None:
        name = payload.name.strip()
        if len(name) < 2:
            raise HTTPException(422, "Ekip adı en az 2 karakter olmalıdır.")
        row.name = name
    if payload.type_id is not None:
        ttype = db.get(EmergencyTeamType, payload.type_id)
        if not ttype or not ttype.is_active:
            raise HTTPException(422, "Geçersiz ekip türü.")
        if ttype.company_id is not None and ttype.company_id != row.company_id:
            raise HTTPException(403, "Bu ekip türü başka firmaya ait.")
        row.type_id = ttype.id
    if payload.min_members is not None:
        row.min_members = payload.min_members
    if payload.notes is not None:
        row.notes = payload.notes.strip() or None
    if payload.leader_assignment_id is not None:
        if payload.leader_assignment_id == 0:
            row.leader_assignment_id = None
        else:
            leader = db.get(EmergencyTeamAssignment, payload.leader_assignment_id)
            if not leader or leader.team_id != row.id or not leader.is_active:
                raise HTTPException(422, "Lider olarak seçilen üye bu ekipte bulunamadı.")
            row.leader_assignment_id = leader.id
            for a in row.assignments or []:
                a.is_leader = a.id == leader.id
    row.updated_at = datetime.utcnow()
    db.commit()
    return _team_response(_load_team(db, row.id))


@router.delete("/teams/{team_id}")
def delete_team(
    team_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load_team(db, team_id)
    ensure_company_access(db, user, row.company_id)
    row.is_active = False
    row.updated_at = datetime.utcnow()
    for a in row.assignments or []:
        a.is_active = False
        a.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "id": team_id}


# --------------------------------------------------------------------------- #
# Assignments (üyeler / destek elemanları)
# --------------------------------------------------------------------------- #
@router.get("/assignments", response_model=list[AssignmentResponse])
def list_assignments(
    company_id: int | None = None,
    team_id: int | None = None,
    q: str | None = None,
    membership: str | None = None,
    shift: str | None = None,
    active_only: bool = True,
    cert_status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    company_ids = company_ids_for_query(db, user, company_id)
    if company_ids == []:
        return []
    stmt = (
        select(EmergencyTeamAssignment)
        .options(
            selectinload(EmergencyTeamAssignment.trainings),
            selectinload(EmergencyTeamAssignment.employee),
            selectinload(EmergencyTeamAssignment.team),
        )
        .order_by(EmergencyTeamAssignment.team_id, EmergencyTeamAssignment.id)
    )
    if company_ids is not None:
        stmt = stmt.where(EmergencyTeamAssignment.company_id.in_(company_ids))
    if team_id:
        stmt = stmt.where(EmergencyTeamAssignment.team_id == team_id)
    if active_only:
        stmt = stmt.where(EmergencyTeamAssignment.is_active.is_(True))
    if membership:
        stmt = stmt.where(EmergencyTeamAssignment.membership == membership.strip().lower())
    if shift:
        stmt = stmt.where(EmergencyTeamAssignment.shift.ilike(f"%{shift.strip()}%"))
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.join(Employee, Employee.id == EmergencyTeamAssignment.employee_id).where(
            or_(
                Employee.full_name.ilike(pattern),
                EmergencyTeamAssignment.role_title.ilike(pattern),
                EmergencyTeamAssignment.section.ilike(pattern),
                EmergencyTeamAssignment.personnel_no.ilike(pattern),
            )
        )
    rows = list(db.scalars(stmt).all())
    workload_cache: dict[int, dict[int, int]] = {}
    out: list[AssignmentResponse] = []
    for r in rows:
        if r.company_id not in workload_cache:
            workload_cache[r.company_id] = employee_active_team_counts(db, r.company_id)
        resp = _assignment_response(r, workload=workload_cache[r.company_id])
        if cert_status and resp.cert_status != cert_status:
            continue
        out.append(resp)
    return out


@router.post("/assignments", response_model=AssignmentResponse)
def create_assignment(
    payload: AssignmentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    ensure_company_access(db, user, payload.company_id)
    team = _load_team(db, payload.team_id)
    if team.company_id != payload.company_id:
        raise HTTPException(422, "Ekip seçilen firmaya ait değil.")
    emp = db.get(Employee, payload.employee_id)
    if not emp or emp.company_id != payload.company_id or not emp.is_active:
        raise HTTPException(422, "Personel seçilen firmada bulunamadı.")
    exists = db.scalar(
        select(EmergencyTeamAssignment).where(
            EmergencyTeamAssignment.team_id == payload.team_id,
            EmergencyTeamAssignment.employee_id == payload.employee_id,
            EmergencyTeamAssignment.is_active.is_(True),
        )
    )
    if exists:
        raise HTTPException(409, "Bu personel zaten bu ekibin üyesi.")

    row = EmergencyTeamAssignment(
        company_id=payload.company_id,
        team_id=payload.team_id,
        employee_id=payload.employee_id,
        membership=payload.membership,
        is_leader=payload.is_leader,
        role_title=payload.role_title,
        shift=payload.shift,
        phone=payload.phone or getattr(emp, "phone", None),
        email=payload.email,
        section=payload.section or getattr(emp, "department", None),
        personnel_no=payload.personnel_no,
        assign_start=payload.assign_start,
        assign_end=payload.assign_end,
        letter_date=payload.letter_date,
        letter_no=payload.letter_no,
        assigned_by=payload.assigned_by,
        notes=payload.notes,
        created_by_id=user.id,
    )
    db.add(row)
    db.flush()
    if payload.is_leader:
        # tek lider: diğerlerini pasifle
        for a in team.assignments or []:
            if a.id != row.id:
                a.is_leader = False
        team.leader_assignment_id = row.id
    db.commit()
    return _assignment_response(_load_assignment(db, row.id))


@router.put("/assignments/{assignment_id}", response_model=AssignmentResponse)
def update_assignment(
    assignment_id: int,
    payload: AssignmentUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load_assignment(db, assignment_id)
    ensure_company_access(db, user, row.company_id)

    if payload.team_id is not None and payload.team_id != row.team_id:
        team = _load_team(db, payload.team_id)
        if team.company_id != row.company_id:
            raise HTTPException(422, "Ekip seçilen firmaya ait değil.")
        row.team_id = team.id
    if payload.membership is not None:
        row.membership = payload.membership
    for attr in (
        "role_title", "shift", "phone", "email", "section", "personnel_no",
        "letter_no", "assigned_by", "notes",
    ):
        val = getattr(payload, attr)
        if val is not None:
            setattr(row, attr, (val.strip() or None) if isinstance(val, str) else val)
    for attr in ("assign_start", "assign_end", "letter_date"):
        val = getattr(payload, attr)
        if val is not None:
            setattr(row, attr, val)
    if payload.is_leader is not None:
        row.is_leader = payload.is_leader
        team = _load_team(db, row.team_id)
        if payload.is_leader:
            for a in team.assignments or []:
                if a.id != row.id:
                    a.is_leader = False
            team.leader_assignment_id = row.id
        elif team.leader_assignment_id == row.id:
            team.leader_assignment_id = None
    row.updated_at = datetime.utcnow()
    db.commit()
    return _assignment_response(_load_assignment(db, row.id))


@router.delete("/assignments/{assignment_id}")
def delete_assignment(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load_assignment(db, assignment_id)
    ensure_company_access(db, user, row.company_id)
    row.is_active = False
    row.updated_at = datetime.utcnow()
    team = db.get(EmergencyTeam, row.team_id)
    if team and team.leader_assignment_id == row.id:
        team.leader_assignment_id = None
    db.commit()
    return {"ok": True, "id": assignment_id}


# --------------------------------------------------------------------------- #
# Trainings
# --------------------------------------------------------------------------- #
@router.get("/assignments/{assignment_id}/trainings", response_model=list[TrainingResponse])
def list_trainings(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    row = _load_assignment(db, assignment_id)
    ensure_company_access(db, user, row.company_id)
    return [
        TrainingResponse.model_validate(t)
        for t in sorted(row.trainings or [], key=lambda x: (x.training_date or x.created_at), reverse=True)
    ]


@router.post("/assignments/{assignment_id}/trainings", response_model=TrainingResponse)
def add_training(
    assignment_id: int,
    payload: TrainingCreate,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load_assignment(db, assignment_id)
    ensure_company_access(db, user, row.company_id)
    training = EmergencyTeamTraining(
        assignment_id=row.id,
        training_type=payload.training_type,
        provider=payload.provider,
        trainer=payload.trainer,
        training_date=payload.training_date,
        duration_hours=payload.duration_hours,
        certificate_no=payload.certificate_no,
        valid_until=payload.valid_until,
        first_aid_cert_no=payload.first_aid_cert_no,
        first_aid_center=payload.first_aid_center,
        first_aid_start=payload.first_aid_start,
        first_aid_end=payload.first_aid_end,
        refresh_date=payload.refresh_date,
        notes=payload.notes,
    )
    db.add(training)
    db.commit()
    db.refresh(training)
    return TrainingResponse.model_validate(training)


@router.post("/assignments/{assignment_id}/certificate-file", response_model=TrainingResponse)
async def upload_certificate(
    assignment_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*EDIT_ROLES)),
):
    row = _load_assignment(db, assignment_id)
    ensure_company_access(db, user, row.company_id)
    name = file.filename or "belge.pdf"
    ext = Path(name).suffix.lower()
    if ext not in ALLOWED_CERT:
        raise HTTPException(422, "Sadece jpg/png/pdf yükleyin.")
    data = await file.read()
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Dosya {settings.max_upload_mb} MB sınırını aşıyor.")
    rel = f"{row.company_id}/emergency_teams/{row.id}_{uuid.uuid4().hex[:10]}{ext}"
    target = _upload_root() / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)

    # En son eğitime iliştir; yoksa belge taşıyan yeni bir kayıt oluştur
    latest = None
    for t in sorted(row.trainings or [], key=lambda x: (x.training_date or x.created_at), reverse=True):
        latest = t
        break
    if latest is not None and not latest.file_path:
        latest.file_path = rel.replace("\\", "/")
        db.commit()
        db.refresh(latest)
        return TrainingResponse.model_validate(latest)
    training = EmergencyTeamTraining(
        assignment_id=row.id,
        training_type="Sertifika belgesi",
        file_path=rel.replace("\\", "/"),
    )
    db.add(training)
    db.commit()
    db.refresh(training)
    return TrainingResponse.model_validate(training)


# --------------------------------------------------------------------------- #
# Exports
# --------------------------------------------------------------------------- #
def _company_teams_payload(db: Session, company_id: int) -> list[dict]:
    teams = _teams_for_company(db, company_id)
    workload = employee_active_team_counts(db, company_id)
    payload: list[dict] = []
    for t in teams:
        resp = _team_response(t, workload=workload)
        members = []
        for a in (t.assignments or []):
            if not a.is_active:
                continue
            m = _assignment_response(a, workload=workload)
            members.append(m.model_dump())
        payload.append({
            "team": t,
            "status": resp.status.model_dump() if resp.status else {},
            "assignments": members,
        })
    return payload


@router.get("/export.xlsx")
def export_xlsx(
    company_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    company_id = ensure_company_access(db, user, company_id)
    company = db.get(Company, company_id)
    payload = _company_teams_payload(db, company_id)
    data = build_teams_excel(company=company, teams_data=payload)
    from io import BytesIO

    return StreamingResponse(
        BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="acil-durum-ekipleri-{company_id}.xlsx"'},
    )


@router.get("/export.pdf")
def export_pdf(
    company_id: int = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    company_id = ensure_company_access(db, user, company_id)
    company = db.get(Company, company_id)
    payload = _company_teams_payload(db, company_id)
    specialist = _specialist_name(db, user, company_id)
    data = build_teams_pdf(company=company, teams_data=payload, specialist=specialist)
    from io import BytesIO

    return StreamingResponse(
        BytesIO(data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="acil-durum-ekipleri-{company_id}.pdf"'},
    )


@router.get("/assignments/{assignment_id}/letter.pdf")
def assignment_letter(
    assignment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    row = _load_assignment(db, assignment_id)
    ensure_company_access(db, user, row.company_id)
    company = db.get(Company, row.company_id)
    team = db.get(EmergencyTeam, row.team_id)
    employee_name = getattr(row.employee, "full_name", None) or "—"
    data = build_assignment_letter_pdf(
        company=company, team=team, assignment=row, employee_name=employee_name
    )
    from io import BytesIO

    return StreamingResponse(
        BytesIO(data),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="gorevlendirme-yazisi-{assignment_id}.pdf"'},
    )
