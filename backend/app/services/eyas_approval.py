"""Eyas Digital Approval — sıralı, hesap bazlı dijital onay motoru.

Nitelikli e-imza değildir. OSGB Signer /esign hattına dokunmaz.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.entities import EyasEvent, EyasStep, EyasWorkflow, User
from app.services.audit import add_audit_log

LEGAL_LABEL = "digital_approval_not_qes"


def _role_fold(label: str) -> str:
    """Türkçe İ/I/ı güvenli karşılaştırma (casefold 'İşveren' → 'işveren' kırılır)."""
    s = (label or "").replace("\u0130", "i").replace("I", "i").replace("\u0131", "i")
    return s.casefold().replace("\u0307", "")


def is_employer_role_label(label: str) -> bool:
    s = _role_fold(label)
    return "işveren" in s or "isveren" in s or "vekil" in s


def is_workplace_employer_account(user: User, company_id: int) -> bool:
    """Son onay yetkisi: işyerine bağlı company_admin (kiosk / işveren vekili)."""
    role = getattr(user.role, "value", str(user.role))
    cid = getattr(user, "company_id", None)
    if cid is None:
        return False
    try:
        if int(cid) != int(company_id):
            return False
    except (TypeError, ValueError):
        return False
    email = (getattr(user, "email", None) or "").casefold()
    if email.endswith("@kiosk.isgsuite.tr"):
        return True
    return role == "company_admin"


def _now() -> datetime:
    return datetime.utcnow()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def last_event_hash(db: Session, workflow_id: int) -> str | None:
    row = db.scalars(
        select(EyasEvent)
        .where(EyasEvent.workflow_id == workflow_id)
        .order_by(EyasEvent.id.desc())
        .limit(1)
    ).first()
    return row.event_hash if row else None


def append_event(
    db: Session,
    *,
    workflow: EyasWorkflow,
    actor: User | None,
    action: str,
    step: EyasStep | None = None,
    payload: dict[str, Any] | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> EyasEvent:
    prev = last_event_hash(db, workflow.id)
    body = {
        "workflow_id": workflow.id,
        "step_id": step.id if step else None,
        "action": action,
        "actor_user_id": actor.id if actor else None,
        "payload": payload or {},
        "prev_hash": prev or "",
        "ts": _now().isoformat() + "Z",
    }
    raw = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    event = EyasEvent(
        workflow_id=workflow.id,
        step_id=step.id if step else None,
        company_id=workflow.company_id,
        actor_user_id=actor.id if actor else None,
        action=action,
        payload_json=json.dumps(payload or {}, ensure_ascii=False),
        prev_hash=prev,
        event_hash=_sha256_text(raw),
        ip_address=ip,
        user_agent=(user_agent or "")[:500] or None,
        created_at=_now(),
    )
    db.add(event)
    return event


def create_workflow(
    db: Session,
    *,
    user: User,
    company_id: int,
    title: str,
    document_kind: str,
    steps: list[dict[str, Any]],
    source_document_id: int | None = None,
    source_sha256: str | None = None,
    source_key: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> EyasWorkflow:
    if not steps:
        raise HTTPException(422, "En az bir onay adımı gerekli.")
    ordered: list[dict[str, Any]] = []
    for idx, raw in enumerate(steps, start=1):
        uid = int(raw["assignee_user_id"])
        assignee = db.get(User, uid)
        if not assignee or not assignee.is_active:
            raise HTTPException(422, f"Adım {idx}: geçerli kullanıcı seçin.")
        ordered.append(
            {
                "step_order": int(raw.get("step_order") or idx),
                "assignee_user_id": uid,
                "role_label": str(raw.get("role_label") or "Onaylayan")[:100],
            }
        )
    ordered.sort(key=lambda x: x["step_order"])
    for i, s in enumerate(ordered, start=1):
        s["step_order"] = i

    now = _now()
    wf = EyasWorkflow(
        company_id=company_id,
        title=title.strip()[:220],
        document_kind=(document_kind or "genel")[:80],
        source_key=(source_key or None),
        source_document_id=source_document_id,
        source_sha256=(source_sha256 or None),
        status="in_progress",
        current_step_order=1,
        legal_label=LEGAL_LABEL,
        created_by_id=user.id,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(wf)
    db.flush()

    for s in ordered:
        st = EyasStep(
            workflow_id=wf.id,
            company_id=company_id,
            step_order=s["step_order"],
            assignee_user_id=s["assignee_user_id"],
            role_label=s["role_label"],
            status="active" if s["step_order"] == 1 else "pending",
            created_at=now,
        )
        db.add(st)
    db.flush()

    append_event(
        db,
        workflow=wf,
        actor=user,
        action="workflow.created",
        payload={
            "title": wf.title,
            "steps": ordered,
            "legal_label": LEGAL_LABEL,
            "notice": "Dijital Onay — nitelikli elektronik imza değildir.",
        },
        ip=ip,
        user_agent=user_agent,
    )
    add_audit_log(
        db,
        user=user,
        action="eyas.workflow.create",
        entity_type="eyas_workflow",
        entity_id=str(wf.id),
        description=f"Eyas dijital onay akışı oluşturuldu: {wf.title}",
        ip_address=ip,
        module="eyas",
    )
    db.commit()
    db.refresh(wf)
    return wf


def soft_delete_workflow(
    db: Session,
    *,
    workflow_id: int,
    user: User,
    ip: str | None = None,
    user_agent: str | None = None,
) -> EyasWorkflow:
    wf = db.get(EyasWorkflow, workflow_id)
    if not wf or not wf.is_active:
        raise HTTPException(404, "Onay akışı bulunamadı.")
    # Uzman / global admin veya oluşturan silebilir (kilitli dahil — test temizliği)
    role = getattr(user.role, "value", str(user.role))
    if role not in {"global_admin", "safety_specialist"} and wf.created_by_id != user.id:
        raise HTTPException(403, "Bu akışı silme yetkiniz yok.")
    prev_status = wf.status
    wf.is_active = False
    if prev_status == "in_progress":
        wf.status = "cancelled"
    wf.updated_at = _now()
    append_event(
        db,
        workflow=wf,
        actor=user,
        action="workflow.deleted",
        payload={"title": wf.title, "previous_status": prev_status},
        ip=ip,
        user_agent=user_agent,
    )
    add_audit_log(
        db,
        user=user,
        action="eyas.workflow.delete",
        entity_type="eyas_workflow",
        entity_id=str(wf.id),
        description=f"Eyas akışı silindi: {wf.title}",
        ip_address=ip,
        module="eyas",
    )
    db.commit()
    db.refresh(wf)
    return wf


def list_steps(db: Session, workflow_id: int) -> list[EyasStep]:
    return list(
        db.scalars(
            select(EyasStep).where(EyasStep.workflow_id == workflow_id).order_by(EyasStep.step_order)
        ).all()
    )


def inbox_for_user(db: Session, user: User, company_ids: list[int] | None) -> list[EyasStep]:
    stmt = (
        select(EyasStep)
        .join(EyasWorkflow, EyasWorkflow.id == EyasStep.workflow_id)
        .where(
            EyasStep.assignee_user_id == user.id,
            EyasStep.status == "active",
            EyasWorkflow.is_active.is_(True),
            EyasWorkflow.status == "in_progress",
        )
        .order_by(EyasStep.id.desc())
    )
    if company_ids is not None:
        if not company_ids:
            return []
        stmt = stmt.where(EyasStep.company_id.in_(company_ids))
    return list(db.scalars(stmt.limit(200)).all())


def _archive_workflow(wf: EyasWorkflow, steps: list[EyasStep], events: list[EyasEvent]) -> str:
    root = Path(settings.upload_dir).resolve()
    rel = f"{wf.company_id}/eyas/workflow_{wf.id}_{_now():%Y%m%d%H%M%S}.json"
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "product": "Eyas Digital Approval",
        "legal_label": LEGAL_LABEL,
        "notice": "Dijital Onay kaydı — nitelikli elektronik imza değildir.",
        "workflow": {
            "id": wf.id,
            "company_id": wf.company_id,
            "title": wf.title,
            "document_kind": wf.document_kind,
            "status": wf.status,
            "source_sha256": wf.source_sha256,
            "locked_at": wf.locked_at.isoformat() + "Z" if wf.locked_at else None,
        },
        "steps": [
            {
                "order": s.step_order,
                "assignee_user_id": s.assignee_user_id,
                "role_label": s.role_label,
                "status": s.status,
                "decided_at": s.decided_at.isoformat() + "Z" if s.decided_at else None,
                "ip_address": s.ip_address,
                "user_agent": s.user_agent,
                "device_note": s.device_note,
                "note": s.note,
            }
            for s in steps
        ],
        "events": [
            {
                "action": e.action,
                "actor_user_id": e.actor_user_id,
                "prev_hash": e.prev_hash,
                "event_hash": e.event_hash,
                "created_at": e.created_at.isoformat() + "Z",
            }
            for e in events
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return rel.replace("\\", "/")


def decide_step(
    db: Session,
    *,
    workflow_id: int,
    user: User,
    approve: bool,
    note: str | None = None,
    device_note: str | None = None,
    ip: str | None = None,
    user_agent: str | None = None,
) -> EyasWorkflow:
    wf = db.get(EyasWorkflow, workflow_id)
    if not wf or not wf.is_active:
        raise HTTPException(404, "Onay akışı bulunamadı.")
    if wf.status != "in_progress":
        raise HTTPException(409, f"Akış onaylanamaz (durum={wf.status}).")

    step = db.scalars(
        select(EyasStep).where(
            EyasStep.workflow_id == wf.id,
            EyasStep.step_order == wf.current_step_order,
            EyasStep.status == "active",
        )
    ).first()
    if not step:
        raise HTTPException(409, "Aktif onay adımı yok.")
    is_employer_step = is_employer_role_label(step.role_label or "")
    # Zincirin son adımı da işveren onayıdır (etiket farklı yazılmış olsa bile)
    has_next = db.scalars(
        select(EyasStep.id).where(
            EyasStep.workflow_id == wf.id,
            EyasStep.step_order == step.step_order + 1,
        )
    ).first()
    is_final_step = has_next is None
    workplace_employer = is_workplace_employer_account(user, wf.company_id)
    employer_may_decide = workplace_employer and (is_employer_step or is_final_step)
    if step.assignee_user_id != user.id and not employer_may_decide:
        raise HTTPException(
            403,
            "Bu son adımı yalnızca işveren / işveren vekili (işyeri hesabı) onaylayabilir.",
        )
    # İşyeri işveren paneli: MFA yoksa da son adım onaylanabilir (kiosk / vekil)
    if not getattr(user, "mfa_enabled", False) and not employer_may_decide:
        raise HTTPException(
            403,
            "Dijital onay için hesapta Authenticator (TOTP) MFA açık olmalıdır. Güvenlik menüsünden etkinleştirin.",
        )

    now = _now()
    step.decided_at = now
    step.ip_address = ip
    step.user_agent = (user_agent or "")[:500] or None
    step.device_note = (device_note or "")[:240] or None
    step.note = (note or "")[:1000] or None

    if not approve:
        step.status = "rejected"
        wf.status = "rejected"
        wf.updated_at = now
        append_event(
            db,
            workflow=wf,
            actor=user,
            action="step.rejected",
            step=step,
            payload={
                "step_order": step.step_order,
                "role_label": step.role_label,
                "full_name": user.full_name,
                "note": step.note,
            },
            ip=ip,
            user_agent=user_agent,
        )
        add_audit_log(
            db,
            user=user,
            action="eyas.step.reject",
            entity_type="eyas_workflow",
            entity_id=str(wf.id),
            description=f"Eyas adım reddedildi: {step.role_label}",
            ip_address=ip,
            module="eyas",
        )
        db.commit()
        db.refresh(wf)
        return wf

    step.status = "approved"
    append_event(
        db,
        workflow=wf,
        actor=user,
        action="step.approved",
        step=step,
        payload={
            "step_order": step.step_order,
            "role_label": step.role_label,
            "full_name": user.full_name,
            "user_role": getattr(user.role, "value", str(user.role)),
            "note": step.note,
            "legal_label": LEGAL_LABEL,
        },
        ip=ip,
        user_agent=user_agent,
    )
    add_audit_log(
        db,
        user=user,
        action="eyas.step.approve",
        entity_type="eyas_workflow",
        entity_id=str(wf.id),
        description=f"Eyas dijital onay: {user.full_name} / {step.role_label}",
        ip_address=ip,
        module="eyas",
        new_value=json.dumps(
            {
                "approver": user.full_name,
                "role_label": step.role_label,
                "at": now.isoformat() + "Z",
                "ip": ip,
            },
            ensure_ascii=False,
        ),
    )

    nxt = db.scalars(
        select(EyasStep).where(
            EyasStep.workflow_id == wf.id,
            EyasStep.step_order == step.step_order + 1,
        )
    ).first()
    if nxt:
        nxt.status = "active"
        wf.current_step_order = nxt.step_order
        wf.updated_at = now
        append_event(
            db,
            workflow=wf,
            actor=user,
            action="step.activated",
            step=nxt,
            payload={"step_order": nxt.step_order, "assignee_user_id": nxt.assignee_user_id},
            ip=ip,
            user_agent=user_agent,
        )
    else:
        wf.status = "locked"
        wf.locked_at = now
        wf.updated_at = now
        steps = list_steps(db, wf.id)
        events = list(
            db.scalars(select(EyasEvent).where(EyasEvent.workflow_id == wf.id).order_by(EyasEvent.id)).all()
        )
        wf.archive_path = _archive_workflow(wf, steps, events)
        append_event(
            db,
            workflow=wf,
            actor=user,
            action="workflow.locked",
            payload={"archive_path": wf.archive_path, "legal_label": LEGAL_LABEL},
            ip=ip,
            user_agent=user_agent,
        )
        add_audit_log(
            db,
            user=user,
            action="eyas.workflow.lock",
            entity_type="eyas_workflow",
            entity_id=str(wf.id),
            description="Eyas dijital onay tamamlandı ve kilitlendi",
            ip_address=ip,
            module="eyas",
        )

    db.commit()
    db.refresh(wf)
    return wf
