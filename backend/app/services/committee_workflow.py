"""OHS committee approval workflow, role-scoped queues and membership lifecycle.

The service reuses Eyas for Specialist → Physician → Employer digital approval,
keeps immutable meeting versions, and never deletes completed signature evidence.
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
)
from app.services import eyas_approval, eyas_workplace
from app.services.audit import add_audit_log
from app.services.committee_meeting_pdf import build_committee_meeting_pdf

MANDATORY_ROLE_CODES = ("igu", "hekim", "isveren_vekili")
REMOVAL_REASONS = {
    "assignment_ended",
    "employment_ended",
    "workplace_changed",
    "role_changed",
    "incorrectly_added",
    "committee_restructured",
    "other",
}


def role_value(user: User) -> str:
    return user.role.value if hasattr(user.role, "value") else str(user.role)


def meeting_row(db: Session, meeting_id: int) -> dict[str, Any]:
    row = db.execute(
        text("SELECT * FROM ohs_committee_meetings WHERE id=:id AND is_active=true"),
        {"id": meeting_id},
    ).mappings().first()
    if not row:
        raise HTTPException(404, "Kurul toplantısı bulunamadı.")
    return dict(row)


def snapshot_members(meeting: dict[str, Any]) -> list[dict[str, Any]]:
    raw = meeting.get("member_snapshot_json")
    if not raw:
        return []
    try:
        parsed = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []
    return parsed if isinstance(parsed, list) else []


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


def assigned_participants(db: Session, company_id: int) -> list[dict[str, Any]]:
    data = eyas_workplace.suggested_assignees(db, company_id)
    participants: list[dict[str, Any]] = []
    for step in data.get("steps") or []:
        user_id = step.get("suggested_user_id")
        if not user_id:
            continue
        user = db.get(User, int(user_id))
        if not user or not user.is_active:
            continue
        participants.append(
            {
                "step_order": int(step["step_order"]),
                "role_key": step.get("role_key"),
                "role_label": step["role_label"],
                "assignee_user_id": user.id,
                "assignee_name": user.full_name,
            }
        )
    return participants


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


def can_manage_company(db: Session, user: User, company_id: int) -> bool:
    role = role_value(user)
    if role == "global_admin":
        return True
    participants = assigned_participants(db, company_id)
    if role == "safety_specialist":
        return any(
            p["role_key"] == "safety_specialist" and p["assignee_user_id"] == user.id
            for p in participants
        )
    if role == "company_admin":
        return any(
            p["role_key"] == "employer_representative" and p["assignee_user_id"] == user.id
            for p in participants
        )
    return False


def assert_can_manage(db: Session, user: User, company_id: int) -> None:
    ensure_company_access(db, user, company_id)
    if not can_manage_company(db, user, company_id):
        raise HTTPException(403, "Bu işyerinin İSG kurulunu yönetme yetkiniz yok.")


def notify_user(
    db: Session,
    *,
    meeting_id: int,
    company_id: int,
    user_id: int | None,
    title: str,
    message: str,
    warning: bool = False,
    critical: bool = False,
) -> None:
    level = NotificationType.CRITICAL if critical else NotificationType.WARNING if warning else NotificationType.INFO
    db.add(
        Notification(
            company_id=company_id,
            user_id=user_id,
            type=level,
            title=title[:220],
            message=message[:1000],
            entity_type="ohs_committee_meeting" if meeting_id else "ohs_committee_member",
            entity_id=str(meeting_id) if meeting_id else None,
        )
    )


def _workflow_data(db: Session, workflow_id: int | None) -> dict[str, Any] | None:
    if not workflow_id:
        return None
    workflow = db.get(EyasWorkflow, workflow_id)
    if not workflow:
        return None
    steps = list(
        db.scalars(
            select(EyasStep)
            .where(EyasStep.workflow_id == workflow.id)
            .order_by(EyasStep.step_order)
        ).all()
    )
    users = {item.id: item for item in db.scalars(select(User).where(User.id.in_({s.assignee_user_id for s in steps}))).all()} if steps else {}
    return {
        "id": workflow.id,
        "status": workflow.status,
        "current_step_order": workflow.current_step_order,
        "source_sha256": workflow.source_sha256,
        "locked_at": workflow.locked_at,
        "steps": [
            {
                "id": step.id,
                "step_order": step.step_order,
                "assignee_user_id": step.assignee_user_id,
                "assignee_name": users.get(step.assignee_user_id).full_name if users.get(step.assignee_user_id) else None,
                "role_label": step.role_label,
                "status": step.status,
                "decided_at": step.decided_at,
                "note": step.note,
            }
            for step in steps
        ],
    }


def _meeting_pdf_hash(db: Session, meeting: dict[str, Any]) -> str:
    company = db.get(Company, meeting["company_id"])
    pdf = build_committee_meeting_pdf(
        company={"name": company.name if company else "—", "address": getattr(company, "address", None)},
        meeting=meeting,
        members=snapshot_members(meeting),
    )
    return hashlib.sha256(pdf).hexdigest()


def _archive_current_version(
    db: Session,
    *,
    meeting: dict[str, Any],
    user: User,
    reason: str,
) -> None:
    version = int(meeting.get("document_version") or 1)
    exists = db.scalar(
        text("""
            SELECT id FROM ohs_committee_meeting_versions
             WHERE meeting_id=:meeting_id AND document_version=:version
        """),
        {"meeting_id": meeting["id"], "version": version},
    )
    if exists:
        return
    from app.services.committee_signature import final_signed_artifact
    artifact = final_signed_artifact(db, meeting["id"], version)
    db.execute(
        text("""
            INSERT INTO ohs_committee_meeting_versions
                (meeting_id, company_id, document_version, meeting_snapshot_json,
                 member_snapshot_json, approval_workflow_id, final_signature_artifact_id,
                 pdf_sha256, archive_reason, created_by_id, created_at)
            VALUES
                (:meeting_id, :company_id, :version, :meeting_snapshot,
                 :member_snapshot, :workflow_id, :artifact_id,
                 :pdf_sha256, :reason, :created_by_id, :created_at)
        """),
        {
            "meeting_id": meeting["id"],
            "company_id": meeting["company_id"],
            "version": version,
            "meeting_snapshot": json.dumps(meeting, ensure_ascii=False, default=str),
            "member_snapshot": meeting.get("member_snapshot_json"),
            "workflow_id": meeting.get("approval_workflow_id"),
            "artifact_id": artifact.id if artifact else None,
            "pdf_sha256": meeting.get("pdf_sha256"),
            "reason": reason[:120],
            "created_by_id": user.id,
            "created_at": datetime.utcnow(),
        },
    )


def submit_for_approval(
    db: Session,
    *,
    meeting_id: int,
    user: User,
    ip: str | None = None,
    user_agent: str | None = None,
) -> dict[str, Any]:
    meeting = meeting_row(db, meeting_id)
    assert_can_manage(db, user, meeting["company_id"])
    if meeting.get("approval_workflow_id"):
        workflow = db.get(EyasWorkflow, meeting["approval_workflow_id"])
        if workflow and workflow.is_active and workflow.status in {"in_progress", "locked"}:
            raise HTTPException(409, "Bu toplantı için aktif veya tamamlanmış bir onay akışı zaten var.")
    participants = suggested_participants(db, meeting["company_id"])
    source_sha256 = _meeting_pdf_hash(db, meeting)
    workflow = eyas_approval.create_workflow(
        db,
        user=user,
        company_id=meeting["company_id"],
        title=meeting.get("title") or f"İSG Kurulu Toplantısı #{meeting_id}",
        document_kind="ohs_committee_meeting",
        steps=[
            {
                "step_order": p["step_order"],
                "assignee_user_id": p["assignee_user_id"],
                "role_label": p["role_label"],
            }
            for p in participants
        ],
        # source_document_id is reserved for document_records. The committee
        # meeting links to this workflow through approval_workflow_id.
        source_document_id=None,
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
        {"workflow_id": workflow.id, "now": now, "sha": source_sha256, "meeting_id": meeting_id},
    )
    for participant in participants:
        notify_user(
            db,
            meeting_id=meeting_id,
            company_id=meeting["company_id"],
            user_id=participant["assignee_user_id"],
            title="İSG Kurulu toplantısı onay akışına gönderildi",
            message=f"{meeting.get('meeting_date')} tarihli toplantıda göreviniz: {participant['role_label']}.",
        )
    notify_user(
        db,
        meeting_id=meeting_id,
        company_id=meeting["company_id"],
        user_id=participants[0]["assignee_user_id"],
        title="İSG Kurulu toplantısı incelemenizi bekliyor",
        message="Onay sırası sizde. Toplantıyı inceleyip onaylayın veya gerekçeli olarak reddedin.",
        warning=True,
    )
    db.commit()
    return work_queue_item(db, meeting_id, user=user)


def sync_from_eyas_transition(db: Session, workflow: EyasWorkflow, actor: User) -> None:
    if workflow.document_kind != "ohs_committee_meeting":
        return
    meeting_id = db.scalar(
        text("SELECT id FROM ohs_committee_meetings WHERE approval_workflow_id=:workflow_id AND is_active=true"),
        {"workflow_id": workflow.id},
    )
    if not meeting_id:
        return
    meeting = meeting_row(db, int(meeting_id))
    steps = list(
        db.scalars(
            select(EyasStep)
            .where(EyasStep.workflow_id == workflow.id)
            .order_by(EyasStep.step_order)
        ).all()
    )
    now = datetime.utcnow()
    if workflow.status == "rejected":
        rejected = next((step for step in steps if step.status == "rejected"), None)
        db.execute(
            text("""
                UPDATE ohs_committee_meetings
                   SET approval_status='rejected', status='draft',
                       approval_current_step=:step, updated_at=:now
                 WHERE id=:id
            """),
            {"step": rejected.step_order if rejected else workflow.current_step_order, "now": now, "id": meeting["id"]},
        )
        for step in steps:
            notify_user(
                db,
                meeting_id=meeting["id"],
                company_id=meeting["company_id"],
                user_id=step.assignee_user_id,
                title="İSG Kurulu toplantısı reddedildi",
                message=f"Toplantı {actor.full_name} tarafından gerekçeli olarak reddedildi.",
                critical=True,
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
        from app.services.committee_signature import initialize_signature_steps
        initialize_signature_steps(db, meeting["id"], workflow)
        for step in steps:
            notify_user(
                db,
                meeting_id=meeting["id"],
                company_id=meeting["company_id"],
                user_id=step.assignee_user_id,
                title="İSG Kurulu toplantısının dijital onayları tamamlandı",
                message="Uzman, hekim ve işveren/vekil onayları tamamlandı. Elektronik imza sırası ayrıca izlenmektedir.",
            )
    else:
        active = next((step for step in steps if step.status == "active"), None)
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
            notify_user(
                db,
                meeting_id=meeting["id"],
                company_id=meeting["company_id"],
                user_id=active.assignee_user_id,
                title="İSG Kurulu toplantısında onay sırası sizde",
                message=f"{active.role_label} adımı inceleme ve onayınızı bekliyor.",
                warning=True,
            )
    db.commit()


def work_queue_item(db: Session, meeting_id: int, *, user: User) -> dict[str, Any]:
    meeting = meeting_row(db, meeting_id)
    ensure_company_access(db, user, meeting["company_id"])
    company = db.get(Company, meeting["company_id"])
    workflow = _workflow_data(db, meeting.get("approval_workflow_id"))
    current_participants = assigned_participants(db, meeting["company_id"])
    participant_ids = {p["assignee_user_id"] for p in current_participants}
    if workflow:
        participant_ids.update(step["assignee_user_id"] for step in workflow["steps"])
    from app.services.committee_signature import workflow_data as signature_workflow_data
    signature_workflow = signature_workflow_data(
        db, meeting_id, int(meeting.get("document_version") or 1), user=user
    )
    if signature_workflow:
        participant_ids.update(step["signer_user_id"] for step in signature_workflow["steps"])
    can_manage = can_manage_company(db, user, meeting["company_id"])
    if user.id not in participant_ids and not can_manage and role_value(user) != "global_admin":
        raise HTTPException(403, "Bu kurul toplantısında görevli veya yetkili değilsiniz.")
    active_approval = next((step for step in (workflow or {}).get("steps", []) if step["status"] == "active"), None)
    active_signature = next((step for step in (signature_workflow or {}).get("steps", []) if step["status"] == "active"), None)
    if active_signature and active_signature["signer_user_id"] == user.id:
        pending_action = "sign"
    elif active_approval and active_approval["assignee_user_id"] == user.id:
        pending_action = "approve"
    elif (workflow and workflow["status"] == "in_progress") or (signature_workflow and signature_workflow["status"] == "in_progress"):
        pending_action = "wait"
    elif can_manage and (not workflow or meeting.get("approval_status") in {"draft", "rejected", "revision_required", "incomplete"}):
        pending_action = "submit"
    else:
        pending_action = "none"
    return {
        "id": meeting["id"],
        "company_id": meeting["company_id"],
        "company_name": company.name if company else None,
        "meeting_date": meeting.get("meeting_date"),
        "title": meeting.get("title") or "İSG Kurulu Toplantısı",
        "meeting_no": meeting.get("meeting_no"),
        "document_no": meeting.get("document_no"),
        "document_version": int(meeting.get("document_version") or 1),
        "status": meeting.get("status") or "draft",
        "approval_status": meeting.get("approval_status") or "draft",
        "signature_status": meeting.get("signature_status") or "not_signed",
        "agenda": meeting.get("agenda"),
        "decisions": meeting.get("decisions"),
        "attendees": meeting.get("attendees"),
        "location": meeting.get("location"),
        "next_meeting_date": meeting.get("next_meeting_date"),
        "participants_snapshot": snapshot_members(meeting),
        "approval_workflow": workflow,
        "signature_workflow": signature_workflow,
        "pending_action": pending_action,
        "current_step": active_signature or active_approval,
        "is_participant": user.id in participant_ids,
        "can_manage": can_manage,
        "pdf_path": f"/api/v1/ohs-committee/meetings/{meeting['id']}/pdf",
    }


def work_queue(db: Session, user: User) -> list[dict[str, Any]]:
    ids = company_ids_for_query(db, user, None)
    if ids == []:
        return []
    statement = "SELECT id FROM ohs_committee_meetings WHERE is_active=true"
    if ids is not None:
        safe_ids = sorted({int(item) for item in ids})
        if not safe_ids:
            return []
        statement += f" AND company_id IN ({','.join(str(item) for item in safe_ids)})"
    statement += " ORDER BY meeting_date DESC, id DESC LIMIT 300"
    meeting_ids = db.execute(text(statement)).scalars().all()
    output: list[dict[str, Any]] = []
    for meeting_id in meeting_ids:
        try:
            output.append(work_queue_item(db, int(meeting_id), user=user))
        except HTTPException as exc:
            if exc.status_code == 403:
                continue
            raise
    return output


def invalidate_approval_for_material_change(
    db: Session,
    *,
    meeting_id: int,
    user: User,
    changed_fields: list[str],
    ip: str | None = None,
) -> dict[str, Any]:
    meeting = meeting_row(db, meeting_id)
    assert_can_manage(db, user, meeting["company_id"])
    _archive_current_version(db, meeting=meeting, user=user, reason="material_change")
    workflow_id = meeting.get("approval_workflow_id")
    if workflow_id:
        workflow = db.get(EyasWorkflow, workflow_id)
        if workflow and workflow.is_active and workflow.status != "locked":
            workflow.is_active = False
            workflow.status = "cancelled"
            workflow.updated_at = datetime.utcnow()
    now = datetime.utcnow()
    old_version = int(meeting.get("document_version") or 1)
    from app.services.committee_signature import invalidate_signature_steps
    invalidate_signature_steps(db, meeting_id, old_version, now)
    new_version = old_version + 1
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
        description="Maddi içerik değişikliği nedeniyle yeni belge sürümü oluşturuldu ve yeniden onay/imza zorunlu oldu.",
        ip_address=ip,
        module="ohs_committee",
        old_value=json.dumps({"document_version": old_version, "workflow_id": workflow_id}, ensure_ascii=False),
        new_value=json.dumps({"document_version": new_version, "changed_fields": changed_fields}, ensure_ascii=False),
    )
    db.commit()
    return meeting_row(db, meeting_id)


def remove_member(
    db: Session,
    *,
    member_id: int,
    user: User,
    reason_code: str,
    reason_text: str | None,
    ip: str | None = None,
) -> dict[str, Any]:
    if reason_code not in REMOVAL_REASONS:
        raise HTTPException(422, "Geçersiz üyelik sonlandırma nedeni.")
    if reason_code == "other" and not (reason_text or "").strip():
        raise HTTPException(422, "Diğer nedeni için kısa açıklama zorunludur.")
    row = db.execute(text("SELECT * FROM ohs_committee_members WHERE id=:id"), {"id": member_id}).mappings().first()
    if not row or not row["is_active"]:
        raise HTTPException(409, "Üyelik zaten sonlandırılmış veya kayıt bulunamıyor.")
    member = dict(row)
    assert_can_manage(db, user, member["company_id"])
    protected = db.scalar(
        text("""
            SELECT m.id
              FROM ohs_committee_meetings m
              LEFT JOIN eyas_workflows w ON w.id=m.approval_workflow_id
             WHERE m.company_id=:company_id AND m.is_active=true
               AND (
                    (w.is_active=true AND w.status='in_progress')
                    OR m.signature_status='waiting_for_signature'
               )
             ORDER BY m.id DESC LIMIT 1
        """),
        {"company_id": member["company_id"]},
    )
    if member.get("is_mandatory") and protected:
        raise HTTPException(
            409,
            "Bu zorunlu üye aktif onay veya elektronik imza akışında. Mevcut sürüm tamamlanmadan ya da revize edilmeden üyelik sonlandırılamaz.",
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
            "end_date": date.today(),
            "now": now,
            "user_id": user.id,
            "reason_code": reason_code,
            "reason_text": (reason_text or "").strip() or None,
            "document_version": int(current_version),
            "id": member_id,
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
        notify_user(
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


def approval_members_for_pdf(
    db: Session,
    meeting: dict[str, Any],
    members: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    workflow = _workflow_data(db, meeting.get("approval_workflow_id"))
    role_map = {
        "İş Güvenliği Uzmanı": "igu",
        "İşyeri Hekimi": "hekim",
        "İşveren / vekili": "isveren_vekili",
        "İşveren / İşveren Vekili": "isveren_vekili",
    }
    approval_by_role = {
        role_map.get(step["role_label"]): step
        for step in (workflow or {}).get("steps", [])
        if role_map.get(step["role_label"])
    }
    signature_by_role: dict[str, dict[str, Any]] = {}
    version = int(meeting.get("document_version") or 1)
    signature_rows = db.execute(
        text("""
            SELECT role_label, status, signed_at, esign_artifact_id
              FROM ohs_committee_signature_steps
             WHERE meeting_id=:meeting_id AND document_version=:version
        """),
        {"meeting_id": meeting["id"], "version": version},
    ).mappings().all()
    for row in signature_rows:
        role_code = role_map.get(row["role_label"])
        if role_code:
            signature_by_role[role_code] = dict(row)
    output: list[dict[str, Any]] = []
    for original in members:
        member = dict(original)
        role_code = member.get("role_code")
        approval = approval_by_role.get(role_code)
        signature = signature_by_role.get(role_code)
        if approval:
            member["approval_status"] = approval["status"]
            member["approved_at"] = approval.get("decided_at")
        if signature and signature["status"] == "signed" and signature.get("esign_artifact_id"):
            member["signature_status"] = "Elektronik olarak imzalandı"
            member["signed_at"] = signature.get("signed_at") or "—"
        elif approval and approval["status"] == "approved":
            member["signature_status"] = "Onaylandı — elektronik imza bekliyor"
            member["signed_at"] = "—"
        elif approval and approval["status"] == "rejected":
            member["signature_status"] = "Reddedildi"
            member["signed_at"] = approval.get("decided_at") or "—"
        elif approval:
            member["signature_status"] = "Onay / imza bekliyor"
        output.append(member)
    return output
