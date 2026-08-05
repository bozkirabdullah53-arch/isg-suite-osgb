"""OHS committee meeting workflow integration and safe membership lifecycle.

The service reuses Eyas for sequential approval and keeps committee meeting/member
history immutable through snapshots and soft deactivation.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.company_access import company_ids_for_query, ensure_company_access
from app.models.entities import (
    Company,
    EyasStep,
    EyasWorkflow,
    Notification,
    NotificationType,
    User,
    UserRole,
)
from app.services import eyas_approval, eyas_workplace
from app.services.audit import add_audit_log
from app.services.committee_meeting_pdf import build_committee_meeting_pdf

MANDATORY_ROLE_CODES = ("igu", "hekim", "isveren_vekili")
MANAGER_ROLES = {"global_admin", "safety_specialist", "company_admin"}
FINAL_MEETING_STATUSES = {"completed", "approved", "signed", "cancelled"}
REMOVAL_REASONS = {
    "assignment_ended",
    "employment_ended",
    "workplace_changed",
    "role_changed",
    "incorrectly_added",
    "committee_restructured",
    "other",
}


def _role_value(user: User) -> str:
    return user.role.value if hasattr(user.role, "value") else str(user.role)


def _meeting(db: Session, meeting_id: int) -> dict[str, Any]:
    row = db.execute(
        text("SELECT * FROM ohs_committee_meetings WHERE id=:id AND is_active=true"),
        {"id": meeting_id},
    ).mappings().first()
    if not row:
        raise HTTPException(404, "Kurul toplantısı bulunamadı.")
    return dict(row)


def _active_member_roles(db: Session, company_id: int) -> set[str]:
    return set(
        db.scalars(
            text("SELECT role_code FROM ohs_committee_members WHERE company_id=:company_id AND is_active=true"),
            {"company_id": company_id},
        ).all()
    )


def missing_mandatory_roles(db: Session, company_id: int) -> list[str]:
    labels = {
        "igu": "İş Güvenliği Uzmanı",
        "hekim": "İşyeri Hekimi",
        "isveren_vekili": "İşveren / İşveren Vekili",
    }
    current = _active_member_roles(db, company_id)
    return [labels[code] for code in MANDATORY_ROLE_CODES if code not in current]


def suggested_participants(db: Session, company_id: int) -> list[dict[str, Any]]:
    missing = missing_mandatory_roles(db, company_id)
    if missing:
        raise HTTPException(409, f"Kurul eksik. Zorunlu üyeler: {', '.join(missing)}")
    data = eyas_workplace.suggested_assignees(db, company_id)
    participants: list[dict[str, Any]] = []
    for step in data.get("steps") or []:
        user_id = step.get("suggested_user_id")
        if not user_id:
            warnings = "; ".join(step.get("warnings") or []) or step.get("role_label")
            raise HTTPException(422, f"Onaycı hesabı eksik ({step.get('role_label')}): {warnings}")
        user = db.get(User, int(user_id))
        if not user or not user.is_active:
            raise HTTPException(422, f"Onaycı hesabı aktif değil: {step.get('role_label')}")
        participants.append(
            {
                "step_order": int(step["step_order"]),
                "role_key": step.get("role_key"),
                "role_label": step["role_label"],
                "assignee_user_id": user.id,
                "assignee_name": user.full_name,
            }
        )
    if len(participants) != 3:
        raise HTTPException(422, "Üç zorunlu onaycı gereklidir: Uzman → Hekim → İşveren/vekil.")
    return participants


def _notify(
    db: Session,
    *,
    meeting_id: int,
    company_id: int,
    user_id: int | None,
    title: str,
    message: str,
    level: NotificationType = NotificationType.INFO,
) -> None:
    db.add(
        Notification(
            company_id=company_id,
            user_id=user_id,
            type=level,
            title=title[:220],
            message=message[:1000],
            entity_type="ohs_committee_meeting",
            entity_id=str(meeting_id),
        )
    )


def _snapshot_members(meeting: dict[str, Any]) -> list[dict[str, Any]]:
    raw = meeting.get("member_snapshot_json")
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


def _meeting_pdf_hash(db: Session, meeting: dict[str, Any]) -> str:
    company = db.get(Company, meeting["company_id"])
    pdf = build_committee_meeting_pdf(
        company={"name": company.name if company else "—", "address": getattr(company, "address", None)},
        meeting=meeting,
        members=_snapshot_members(meeting),
    )
    return hashlib.sha256(pdf).hexdigest()


def submit_for_approval(
    db: Session,
    *,
    meeting_id: int,
    user: User,
    ip: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    meeting = _meeting(db, meeting_id)
    ensure_company_access(db, user, meeting["company_id"])
    if _role_value(user) not in MANAGER_ROLES:
        raise HTTPException(403, "Toplantıyı onaya gönderme yetkiniz yok.")
    if meeting.get("approval_workflow_id"):
        wf = db.get(EyasWorkflow, meeting["approval_workflow_id"])
        if wf and wf.is_active and wf.status in {"in_progress", "locked"}:
            raise HTTPException(409, "Bu toplantı için aktif veya tamamlanmış bir onay akışı zaten var.")

    participants = suggested_participants(db, meeting["company_id"])
    source_sha256 = _meeting_pdf_hash(db, meeting)
    steps = [
        {
            "step_order": p["step_order"],
            "assignee_user_id": p["assignee_user_id"],
            "role_label": p["role_label"],
        }
        for p in participants
    ]
    wf = eyas_approval.create_workflow(
        db,
        user=user,
        company_id=meeting["company_id"],
        title=meeting.get("title") or f"İSG Kurulu Toplantısı #{meeting_id}",
        document_kind="ohs_committee_meeting",
        steps=steps,
        source_document_id=meeting_id,
        source_sha256=source_sha256,
        source_key=None,
        ip=ip,
        user_agent=user_agent,
    )
    now = datetime.utcnow()
    db.execute(
        text("""
            UPDATE ohs_committee_meetings
               SET approval_workflow_id=:workflow_id,
                   approval_status='waiting_for_review',
                   approval_current_step=1,
                   approval_submitted_at=:now,
                   approval_completed_at=NULL,
                   approval_invalidated_at=NULL,
                   status='awaiting_approval',
                   signature_status='not_signed',
                   pdf_sha256=:sha,
                   updated_at=:now
             WHERE id=:meeting_id
        """),
        {"workflow_id": wf.id, "now": now, "sha": source_sha256, "meeting_id": meeting_id},
    )
    for participant in participants:
        _notify(
            db,
            meeting_id=meeting_id,
            company_id=meeting["company_id"],
            user_id=participant["assignee_user_id"],
            title="İSG Kurulu toplantısı onay akışına gönderildi",
            message=(
                f"{meeting.get('meeting_date')} tarihli kurul toplantısı onay akışında. "
                f"Göreviniz: {participant['role_label']}."
            ),
        )
    first = participants[0]
    _notify(
        db,
        meeting_id=meeting_id,
        company_id=meeting["company_id"],
        user_id=first["assignee_user_id"],
        title="İSG Kurulu toplantısı incelemenizi bekliyor",
        message="Onay sırası sizde. Toplantı tutanağını inceleyip onaylayın veya gerekçeli olarak reddedin.",
        level=NotificationType.WARNING,
    )
    db.commit()
    return work_queue_item(db, meeting_id, user=user, include_manager=True)


def sync_from_eyas_transition(db: Session, workflow: EyasWorkflow, actor: User) -> None:
    """Mirror an Eyas decision into its committee meeting and emit notifications."""
    if workflow.document_kind != "ohs_committee_meeting" or not workflow.source_document_id:
        return
    meeting = _meeting(db, int(workflow.source_document_id))
    steps = list(
        db.scalars(select(EyasStep).where(EyasStep.workflow_id == workflow.id).order_by(EyasStep.step_order)).all()
    )
    now = datetime.utcnow()
    if workflow.status == "rejected":
        db.execute(
            text("""
                UPDATE ohs_committee_meetings
                   SET approval_status='rejected', status='draft',
                       approval_current_step=:step, updated_at=:now
                 WHERE id=:id
            """),
            {"step": workflow.current_step_order, "now": now, "id": meeting["id"]},
        )
        for step in steps:
            _notify(
                db,
                meeting_id=meeting["id"], company_id=meeting["company_id"],
                user_id=step.assignee_user_id,
                title="İSG Kurulu toplantısı reddedildi",
                message=f"Toplantı {actor.full_name} tarafından gerekçeli olarak reddedildi.",
                level=NotificationType.CRITICAL,
            )
    elif workflow.status == "locked":
        db.execute(
            text("""
                UPDATE ohs_committee_meetings
                   SET approval_status='approved', status='approved',
                       approval_current_step=NULL, approval_completed_at=:now,
                       updated_at=:now
                 WHERE id=:id
            """),
            {"now": now, "id": meeting["id"]},
        )
        for step in steps:
            _notify(
                db,
                meeting_id=meeting["id"], company_id=meeting["company_id"],
                user_id=step.assignee_user_id,
                title="İSG Kurulu toplantısı onaylandı",
                message="Uzman, hekim ve işveren/vekil dijital onay adımları tamamlandı. E-imza durumu ayrıca izlenir.",
            )
    else:
        active = next((s for s in steps if s.status == "active"), None)
        db.execute(
            text("""
                UPDATE ohs_committee_meetings
                   SET approval_status='waiting_for_approval',
                       approval_current_step=:step, updated_at=:now
                 WHERE id=:id
            """),
            {"step": active.step_order if active else workflow.current_step_order, "now": now, "id": meeting["id"]},
        )
        if active:
            _notify(
                db,
                meeting_id=meeting["id"], company_id=meeting["company_id"],
                user_id=active.assignee_user_id,
                title="İSG Kurulu toplantısında onay sırası sizde",
                message=f"{active.role_label} adımı inceleme ve onayınızı bekliyor.",
                level=NotificationType.WARNING,
            )
    db.commit()


def _workflow_data(db: Session, workflow_id: int | None) -> dict[str, Any] | None:
    if not workflow_id:
        return None
    wf = db.get(EyasWorkflow, workflow_id)
    if not wf:
        return None
    steps = list(
        db.scalars(select(EyasStep).where(EyasStep.workflow_id == wf.id).order_by(EyasStep.step_order)).all()
    )
    return {
        "id": wf.id,
        "status": wf.status,
        "current_step_order": wf.current_step_order,
        "locked_at": wf.locked_at,
        "steps": [
            {
                "id": s.id,
                "step_order": s.step_order,
                "assignee_user_id": s.assignee_user_id,
                "assignee_name": (db.get(User, s.assignee_user_id).full_name if db.get(User, s.assignee_user_id) else None),
                "role_label": s.role_label,
                "status": s.status,
                "decided_at": s.decided_at,
                "note": s.note,
            }
            for s in steps
        ],
    }


def work_queue_item(
    db: Session,
    meeting_id: int,
    *,
    user: User,
    include_manager: bool = False,
) -> dict[str, Any]:
    meeting = _meeting(db, meeting_id)
    ensure_company_access(db, user, meeting["company_id"])
    company = db.get(Company, meeting["company_id"])
    workflow = _workflow_data(db, meeting.get("approval_workflow_id"))
    participants: list[dict[str, Any]] = []
    try:
        participants = suggested_participants(db, meeting["company_id"])
    except HTTPException:
        participants = []
    participant_ids = {int(p["assignee_user_id"]) for p in participants}
    if workflow:
        participant_ids.update(int(s["assignee_user_id"]) for s in workflow["steps"])
    is_manager = _role_value(user) in MANAGER_ROLES
    if user.id not in participant_ids and not (include_manager and is_manager):
        raise HTTPException(403, "Bu kurul toplantısında görevli veya yetkili değilsiniz.")
    active_step = None
    if workflow:
        active_step = next((s for s in workflow["steps"] if s["status"] == "active"), None)
    mine = user.id in participant_ids
    return {
        "id": meeting["id"],
        "company_id": meeting["company_id"],
        "company_name": company.name if company else None,
        "meeting_date": meeting.get("meeting_date"),
        "title": meeting.get("title") or "İSG Kurulu Toplantısı",
        "meeting_no": meeting.get("meeting_no"),
        "document_no": meeting.get("document_no"),
        "document_version": meeting.get("document_version") or 1,
        "status": meeting.get("status") or "draft",
        "approval_status": meeting.get("approval_status") or "draft",
        "signature_status": meeting.get("signature_status") or "not_signed",
        "agenda": meeting.get("agenda"),
        "decisions": meeting.get("decisions"),
        "attendees": meeting.get("attendees"),
        "location": meeting.get("location"),
        "next_meeting_date": meeting.get("next_meeting_date"),
        "approval_workflow": workflow,
        "pending_action": (
            "approve" if active_step and active_step["assignee_user_id"] == user.id else
            "wait" if workflow and workflow["status"] == "in_progress" else
            "submit" if is_manager and not workflow else
            "none"
        ),
        "current_step": active_step,
        "is_participant": mine,
        "can_manage": is_manager,
        "pdf_path": f"/api/v1/ohs-committee/meetings/{meeting['id']}/pdf",
    }


def work_queue(db: Session, user: User) -> list[dict[str, Any]]:
    ids = company_ids_for_query(db, user, None)
    if ids == []:
        return []
    stmt = "SELECT id FROM ohs_committee_meetings WHERE is_active=true"
    params: dict[str, Any] = {}
    if ids is not None:
        stmt += " AND company_id = ANY(:company_ids)" if db.bind and db.bind.dialect.name == "postgresql" else " AND company_id IN (%s)" % ",".join(str(int(i)) for i in ids)
        if db.bind and db.bind.dialect.name == "postgresql":
            params["company_ids"] = ids
    stmt += " ORDER BY meeting_date DESC, id DESC LIMIT 300"
    rows = db.execute(text(stmt), params).scalars().all()
    out: list[dict[str, Any]] = []
    include_manager = _role_value(user) in MANAGER_ROLES
    for meeting_id in rows:
        try:
            out.append(work_queue_item(db, int(meeting_id), user=user, include_manager=include_manager))
        except HTTPException as exc:
            if exc.status_code == 403:
                continue
            raise
    return out


def invalidate_approval_for_material_change(
    db: Session,
    *,
    meeting_id: int,
    user: User,
    changed_fields: list[str],
    ip: str | None = None,
) -> dict[str, Any]:
    meeting = _meeting(db, meeting_id)
    ensure_company_access(db, user, meeting["company_id"])
    if _role_value(user) not in MANAGER_ROLES:
        raise HTTPException(403, "Toplantıyı değiştirme yetkiniz yok.")
    workflow_id = meeting.get("approval_workflow_id")
    if workflow_id:
        wf = db.get(EyasWorkflow, workflow_id)
        if wf and wf.status == "locked":
            # Preserve the completed workflow and detach it from the new document version.
            wf.is_active = True
        elif wf and wf.is_active:
            wf.is_active = False
            wf.status = "cancelled"
            wf.updated_at = datetime.utcnow()
    now = datetime.utcnow()
    new_version = int(meeting.get("document_version") or 1) + 1
    db.execute(
        text("""
            UPDATE ohs_committee_meetings
               SET approval_workflow_id=NULL, approval_status='revision_required',
                   approval_current_step=NULL, approval_invalidated_at=:now,
                   approval_completed_at=NULL, signature_status='not_signed',
                   status='draft', document_version=:version, updated_at=:now
             WHERE id=:id
        """),
        {"now": now, "version": new_version, "id": meeting_id},
    )
    add_audit_log(
        db,
        user=user,
        action="committee.meeting.approval.invalidate",
        entity_type="ohs_committee_meeting",
        entity_id=str(meeting_id),
        description="Maddi içerik değişikliği nedeniyle onay/imza akışı yeni sürüm için sıfırlandı.",
        ip_address=ip,
        module="ohs_committee",
        old_value=json.dumps({"document_version": meeting.get("document_version"), "workflow_id": workflow_id}, ensure_ascii=False),
        new_value=json.dumps({"document_version": new_version, "changed_fields": changed_fields}, ensure_ascii=False),
    )
    db.commit()
    return _meeting(db, meeting_id)


def remove_member(
    db: Session,
    *,
    member_id: int,
    user: User,
    reason_code: str,
    reason_text: str | None,
    ip: str | None = None,
) -> dict[str, Any]:
    role = _role_value(user)
    if role not in MANAGER_ROLES:
        raise HTTPException(403, "Kurul üyeliğini sonlandırma yetkiniz yok.")
    if reason_code not in REMOVAL_REASONS:
        raise HTTPException(422, "Geçersiz üyelik sonlandırma nedeni.")
    if reason_code == "other" and not (reason_text or "").strip():
        raise HTTPException(422, "Diğer nedeni için kısa açıklama zorunludur.")
    row = db.execute(
        text("SELECT * FROM ohs_committee_members WHERE id=:id"), {"id": member_id}
    ).mappings().first()
    if not row or not row["is_active"]:
        raise HTTPException(409, "Üyelik zaten sonlandırılmış veya kayıt bulunamıyor.")
    member = dict(row)
    ensure_company_access(db, user, member["company_id"])

    active_flow = db.execute(
        text("""
            SELECT m.id, m.approval_workflow_id
              FROM ohs_committee_meetings m
              JOIN eyas_workflows w ON w.id=m.approval_workflow_id
             WHERE m.company_id=:company_id AND m.is_active=true
               AND w.is_active=true AND w.status='in_progress'
             ORDER BY m.id DESC LIMIT 1
        """),
        {"company_id": member["company_id"]},
    ).mappings().first()
    if member.get("is_mandatory") and active_flow:
        raise HTTPException(
            409,
            "Bu zorunlu üye aktif bir toplantı onay akışında. Akış tamamlanmadan veya yeni belge sürümü oluşturulmadan üyelik sonlandırılamaz.",
        )

    previous_missing = missing_mandatory_roles(db, member["company_id"])
    current_version = db.scalar(
        text("SELECT max(document_version) FROM ohs_committee_meetings WHERE company_id=:company_id"),
        {"company_id": member["company_id"]},
    ) or 1
    now = datetime.utcnow()
    db.execute(
        text("""
            UPDATE ohs_committee_members
               SET is_active=false,
                   end_date=COALESCE(end_date, :end_date),
                   removed_at=:now,
                   removed_by_id=:user_id,
                   removal_reason_code=:reason_code,
                   removal_reason_text=:reason_text,
                   removal_document_version=:document_version
             WHERE id=:id AND is_active=true
        """),
        {
            "end_date": date.today(), "now": now, "user_id": user.id,
            "reason_code": reason_code, "reason_text": (reason_text or "").strip() or None,
            "document_version": int(current_version), "id": member_id,
        },
    )
    if member.get("is_mandatory"):
        db.execute(
            text("""
                UPDATE ohs_committee_meetings
                   SET status='draft', approval_status='incomplete', updated_at=:now
                 WHERE company_id=:company_id AND is_active=true
                   AND lower(status) NOT IN ('completed','approved','signed','cancelled')
            """),
            {"now": now, "company_id": member["company_id"]},
        )
    new_missing = missing_mandatory_roles(db, member["company_id"])
    audit_payload = {
        "committee_company_id": member["company_id"],
        "membership_id": member_id,
        "removed_person": member["full_name"],
        "removed_role": member["role_code"],
        "removed_by_user_id": user.id,
        "removed_at": now.isoformat() + "Z",
        "reason_code": reason_code,
        "reason_text": (reason_text or "").strip() or None,
        "previous_missing_mandatory": previous_missing,
        "new_missing_mandatory": new_missing,
        "document_version": int(current_version),
    }
    add_audit_log(
        db,
        user=user,
        action="committee.member.remove",
        entity_type="ohs_committee_member",
        entity_id=str(member_id),
        description=f"Kurul üyeliği sonlandırıldı: {member['full_name']} / {member['role_code']}",
        ip_address=ip,
        module="ohs_committee",
        old_value=json.dumps({"is_active": True, "missing_mandatory": previous_missing}, ensure_ascii=False),
        new_value=json.dumps(audit_payload, ensure_ascii=False),
    )
    if member.get("user_id"):
        _notify(
            db,
            meeting_id=0,
            company_id=member["company_id"],
            user_id=member["user_id"],
            title="İSG Kurulu üyeliğiniz sonlandırıldı",
            message=f"Kurul üyeliğiniz {date.today().isoformat()} tarihi itibarıyla sonlandırıldı.",
        )
    db.commit()
    return {
        "ok": True,
        "member_id": member_id,
        "full_name": member["full_name"],
        "role_code": member["role_code"],
        "mandatory": bool(member.get("is_mandatory")),
        "committee_incomplete": bool(new_missing),
        "missing_mandatory": new_missing,
        "message": "Kurul üyesi başarıyla çıkarıldı.",
    }


def approval_members_for_pdf(db: Session, meeting: dict[str, Any], members: list[dict[str, Any]]) -> list[dict[str, Any]]:
    workflow = _workflow_data(db, meeting.get("approval_workflow_id"))
    if not workflow:
        return members
    role_map = {
        "İş Güvenliği Uzmanı": "igu",
        "İşyeri Hekimi": "hekim",
        "İşveren / vekili": "isveren_vekili",
        "İşveren / İşveren Vekili": "isveren_vekili",
    }
    step_by_role = {role_map.get(step["role_label"]): step for step in workflow["steps"]}
    out = []
    for original in members:
        member = dict(original)
        step = step_by_role.get(member.get("role_code"))
        if step:
            member["approval_status"] = step["status"]
            member["approved_at"] = step.get("decided_at")
            if step["status"] == "approved":
                member["signature_status"] = "Onaylandı — elektronik imza tamamlanmadı"
                member["signed_at"] = "—"
            elif step["status"] == "rejected":
                member["signature_status"] = "Reddedildi"
                member["signed_at"] = step.get("decided_at") or "—"
            else:
                member["signature_status"] = "Onay / imza bekliyor"
        out.append(member)
    return out
