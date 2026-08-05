"""Distinct return-for-correction action over the existing EYAS decision engine."""
from __future__ import annotations

import json
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.company_access import ensure_company_access
from app.models.entities import EyasStep, EyasWorkflow, User
from app.services import eyas_approval
from app.services.audit import add_audit_log
from app.services.committee_workflow import meeting_row, notify_user, work_queue_item


def return_for_correction(
    db: Session,
    *,
    meeting_id: int,
    user: User,
    reason: str,
    device_note: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
):
    clean_reason = (reason or "").strip()
    if not clean_reason:
        raise HTTPException(422, "Düzeltmeye iade gerekçesi zorunludur.")
    meeting = meeting_row(db, meeting_id)
    ensure_company_access(db, user, meeting["company_id"])
    workflow_id = meeting.get("approval_workflow_id")
    if not workflow_id:
        raise HTTPException(409, "Aktif kurul onay akışı bulunamadı.")
    workflow = db.get(EyasWorkflow, workflow_id)
    if not workflow or not workflow.is_active or workflow.document_kind != "ohs_committee_meeting":
        raise HTTPException(409, "Kurul toplantısının onay akışı kullanılamıyor.")

    rejected_step_order = int(workflow.current_step_order or 1)
    workflow = eyas_approval.decide_step(
        db,
        workflow_id=workflow.id,
        user=user,
        approve=False,
        note=f"[DÜZELTMEYE İADE] {clean_reason}"[:1000],
        device_note=device_note,
        ip=ip,
        user_agent=user_agent,
    )
    now = datetime.utcnow()
    db.execute(
        text("""
            UPDATE ohs_committee_meetings
               SET approval_status='returned_for_correction',
                   status='draft', signature_status='not_signed',
                   approval_current_step=:step_order, updated_at=:now
             WHERE id=:meeting_id
        """),
        {"step_order": rejected_step_order, "now": now, "meeting_id": meeting_id},
    )
    steps = list(
        db.scalars(
            select(EyasStep)
            .where(EyasStep.workflow_id == workflow.id)
            .order_by(EyasStep.step_order)
        ).all()
    )
    for step in steps:
        notify_user(
            db,
            meeting_id=meeting_id,
            company_id=meeting["company_id"],
            user_id=step.assignee_user_id,
            title="İSG Kurulu toplantısı düzeltmeye iade edildi",
            message=f"{user.full_name} toplantıyı düzeltmeye iade etti. Gerekçe: {clean_reason}",
            warning=True,
        )
    add_audit_log(
        db,
        user=user,
        action="committee.meeting.return_for_correction",
        entity_type="ohs_committee_meeting",
        entity_id=str(meeting_id),
        description="İSG Kurulu toplantısı gerekçeli olarak düzeltmeye iade edildi.",
        ip_address=ip,
        module="ohs_committee",
        old_value=json.dumps(
            {
                "approval_status": meeting.get("approval_status"),
                "status": meeting.get("status"),
                "workflow_id": workflow_id,
                "current_step": rejected_step_order,
            },
            ensure_ascii=False,
        ),
        new_value=json.dumps(
            {
                "approval_status": "returned_for_correction",
                "status": "draft",
                "reason": clean_reason,
            },
            ensure_ascii=False,
        ),
    )
    db.commit()
    return work_queue_item(db, meeting_id, user=user)
