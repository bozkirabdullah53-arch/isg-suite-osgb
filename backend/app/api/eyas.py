"""Eyas Digital Approval API — bayrakla anında kapatılabilir."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.api.company_access import company_ids_for_query, ensure_company_access
from app.api.deps import get_current_user, require_roles
from app.core.config import eyas_digital_approval_active
from app.core.database import get_db
from app.models.entities import EyasEvent, EyasStep, EyasWorkflow, User, UserRole
from app.schemas.eyas import (
    EyasAssigneesOut,
    EyasDecideBody,
    EyasDocsOut,
    EyasEventOut,
    EyasMetaOut,
    EyasStepOut,
    EyasWorkflowCreate,
    EyasWorkflowOut,
)
from app.services import eyas_approval as svc
from app.services import eyas_workplace as workplace

router = APIRouter(prefix="/eyas", tags=["Eyas Digital Approval"])

CREATE_ROLES = (UserRole.GLOBAL_ADMIN, UserRole.SAFETY_SPECIALIST)
VIEW_ROLES = (
    UserRole.GLOBAL_ADMIN,
    UserRole.SAFETY_SPECIALIST,
    UserRole.WORKPLACE_PHYSICIAN,
    UserRole.COMPANY_ADMIN,
)


def _require_eyas() -> None:
    if not eyas_digital_approval_active():
        raise HTTPException(
            503,
            "Eyas Digital Approval kapalı (EYAS_DIGITAL_APPROVAL_FORCE_OFF veya ENABLED=false).",
        )


def _client_ip(request: Request) -> str | None:
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        return xff.split(",")[0].strip()[:64]
    if request.client:
        return (request.client.host or "")[:64] or None
    return None


def _ua(request: Request) -> str | None:
    return (request.headers.get("user-agent") or "")[:500] or None


def _assignee_name(db: Session, user_id: int) -> str | None:
    user = db.get(User, user_id)
    return user.full_name if user else None


def _step_out(db: Session, step: EyasStep) -> EyasStepOut:
    return EyasStepOut(
        id=step.id,
        workflow_id=step.workflow_id,
        company_id=step.company_id,
        step_order=step.step_order,
        assignee_user_id=step.assignee_user_id,
        assignee_name=_assignee_name(db, step.assignee_user_id),
        role_label=step.role_label,
        status=step.status,
        decided_at=step.decided_at,
        ip_address=step.ip_address,
        user_agent=step.user_agent,
        device_note=step.device_note,
        note=step.note,
        created_at=step.created_at,
    )


def _doc_path(db: Session, workflow: EyasWorkflow) -> str | None:
    if workflow.document_kind == "ohs_committee_meeting":
        meeting_id = db.scalar(
            text("SELECT id FROM ohs_committee_meetings WHERE approval_workflow_id=:workflow_id AND is_active=true"),
            {"workflow_id": workflow.id},
        )
        if meeting_id:
            return f"/api/v1/ohs-committee/meetings/{meeting_id}/pdf"
    if not workflow.source_key:
        return None
    return f"/api/v1/eyas/workflows/{workflow.id}/document"


def _wf_out(db: Session, workflow: EyasWorkflow) -> EyasWorkflowOut:
    steps = svc.list_steps(db, workflow.id)
    return EyasWorkflowOut(
        id=workflow.id,
        company_id=workflow.company_id,
        title=workflow.title,
        document_kind=workflow.document_kind,
        source_key=getattr(workflow, "source_key", None),
        source_document_id=workflow.source_document_id,
        source_sha256=workflow.source_sha256,
        status=workflow.status,
        current_step_order=workflow.current_step_order,
        legal_label=workflow.legal_label,
        qes_request_id=workflow.qes_request_id,
        archive_path=workflow.archive_path,
        locked_at=workflow.locked_at,
        created_by_id=workflow.created_by_id,
        is_active=workflow.is_active,
        created_at=workflow.created_at,
        updated_at=workflow.updated_at,
        steps=[_step_out(db, step) for step in steps],
        document_download_path=_doc_path(db, workflow),
    )


@router.get("/meta", response_model=EyasMetaOut)
def meta(user: User = Depends(get_current_user)):
    _ = user
    return EyasMetaOut(enabled=eyas_digital_approval_active())


@router.get("/workplaces/{company_id}/documents", response_model=EyasDocsOut)
def workplace_documents(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    _require_eyas()
    ensure_company_access(db, user, company_id)
    return workplace.list_approval_documents(db, company_id)


@router.get("/workplaces/{company_id}/assignees", response_model=EyasAssigneesOut)
def workplace_assignees(
    company_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    _require_eyas()
    ensure_company_access(db, user, company_id)
    return workplace.suggested_assignees(db, company_id)


@router.get("/workflows", response_model=list[EyasWorkflowOut])
def list_workflows(
    company_id: int | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    _require_eyas()
    ids = company_ids_for_query(db, user, company_id)
    statement = (
        select(EyasWorkflow)
        .where(EyasWorkflow.is_active.is_(True))
        .order_by(EyasWorkflow.id.desc())
    )
    if ids == []:
        return []
    if ids is not None:
        statement = statement.where(EyasWorkflow.company_id.in_(ids))
    if user.role == UserRole.COMPANY_ADMIN:
        own_ids = {
            step.workflow_id
            for step in db.scalars(
                select(EyasStep).where(EyasStep.assignee_user_id == user.id)
            ).all()
        }
        rows = list(db.scalars(statement.limit(300)).all())
        rows = [row for row in rows if row.created_by_id == user.id or row.id in own_ids]
        return [_wf_out(db, row) for row in rows[:100]]
    return [_wf_out(db, row) for row in db.scalars(statement.limit(100)).all()]


@router.get("/inbox", response_model=list[EyasWorkflowOut])
def inbox(
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    _require_eyas()
    ids = company_ids_for_query(db, user, None)
    steps = svc.inbox_for_user(db, user, ids)
    output: list[EyasWorkflowOut] = []
    seen: set[int] = set()
    for step in steps:
        if step.workflow_id in seen:
            continue
        workflow = db.get(EyasWorkflow, step.workflow_id)
        if workflow:
            output.append(_wf_out(db, workflow))
            seen.add(workflow.id)
    return output


@router.post("/workflows", response_model=EyasWorkflowOut)
def create_workflow(
    payload: EyasWorkflowCreate,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*CREATE_ROLES)),
):
    _require_eyas()
    ensure_company_access(db, user, payload.company_id)
    title = (payload.title or "").strip()
    document_kind = (payload.document_kind or "genel").strip() or "genel"
    source_key = (payload.source_key or "").strip() or None
    source_document_id = payload.source_document_id
    steps_in = [step.model_dump() for step in (payload.steps or [])]
    if source_key:
        try:
            document = workplace.resolve_document(db, payload.company_id, source_key)
        except KeyError:
            raise HTTPException(422, "Seçilen belge bu işyerinde bulunamadı.") from None
        if document.get("readiness") != "ready":
            raise HTTPException(
                422,
                document.get("readiness_detail") or "Rapor hazır değil. Önce ilgili modülde belgeyi tamamlayın.",
            )
        title = title or document["title"]
        document_kind = document["kind"]
        if document.get("document_record_id"):
            source_document_id = document["document_record_id"]
    if not title or len(title) < 2:
        raise HTTPException(422, "Belge seçin veya başlık girin.")
    if not steps_in:
        suggested = workplace.suggested_assignees(db, payload.company_id)
        built = []
        for step in suggested["steps"]:
            user_id = step.get("suggested_user_id")
            if not user_id:
                warning = "; ".join(step.get("warnings") or []) or step["role_label"]
                raise HTTPException(422, f"Onaycı eksik ({step['role_label']}): {warning}")
            built.append({
                "assignee_user_id": user_id,
                "role_label": step["role_label"],
                "step_order": step["step_order"],
            })
        steps_in = built
    elif payload.auto_assignees and source_key:
        suggested = workplace.suggested_assignees(db, payload.company_id)
        built = []
        for step in suggested["steps"]:
            user_id = step.get("suggested_user_id")
            if not user_id:
                warning = "; ".join(step.get("warnings") or []) or step["role_label"]
                raise HTTPException(422, f"Onaycı eksik ({step['role_label']}): {warning}")
            built.append({
                "assignee_user_id": user_id,
                "role_label": step["role_label"],
                "step_order": step["step_order"],
            })
        for index, step in enumerate(steps_in[:3]):
            if step.get("assignee_user_id"):
                built[index]["assignee_user_id"] = int(step["assignee_user_id"])
                if step.get("role_label"):
                    built[index]["role_label"] = step["role_label"]
        steps_in = built
    if source_key and len(steps_in) < 3:
        raise HTTPException(422, "Üç onaycı gerekli: İş Güvenliği → Hekim → İşveren/vekil.")
    if not steps_in:
        raise HTTPException(422, "En az bir onay adımı gerekli.")
    workflow = svc.create_workflow(
        db,
        user=user,
        company_id=payload.company_id,
        title=title,
        document_kind=document_kind,
        steps=steps_in,
        source_document_id=source_document_id,
        source_sha256=payload.source_sha256,
        source_key=source_key,
        ip=_client_ip(request),
        user_agent=_ua(request),
    )
    return _wf_out(db, workflow)


@router.get("/workflows/{workflow_id}", response_model=EyasWorkflowOut)
def get_workflow(
    workflow_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    _require_eyas()
    workflow = db.get(EyasWorkflow, workflow_id)
    if not workflow or not workflow.is_active:
        raise HTTPException(404, "Onay akışı bulunamadı.")
    ensure_company_access(db, user, workflow.company_id)
    return _wf_out(db, workflow)


@router.get("/workflows/{workflow_id}/document")
def get_workflow_document(
    workflow_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    _require_eyas()
    workflow = db.get(EyasWorkflow, workflow_id)
    if not workflow or not workflow.is_active:
        raise HTTPException(404, "Onay akışı bulunamadı.")
    ensure_company_access(db, user, workflow.company_id)
    if workflow.document_kind == "ohs_committee_meeting":
        meeting_id = db.scalar(
            text("SELECT id FROM ohs_committee_meetings WHERE approval_workflow_id=:workflow_id AND is_active=true"),
            {"workflow_id": workflow.id},
        )
        if not meeting_id:
            raise HTTPException(404, "Kurul toplantısı bağlantısı bulunamadı.")
        return RedirectResponse(
            url=f"/api/v1/ohs-committee/meetings/{meeting_id}/pdf",
            status_code=307,
        )
    if not workflow.source_key:
        raise HTTPException(404, "Bu akışa bağlı belge kaynağı yok.")
    try:
        document = workplace.resolve_document(db, workflow.company_id, workflow.source_key)
    except KeyError:
        raise HTTPException(404, "Kaynak belge bulunamadı.") from None
    if document.get("readiness") == "missing":
        raise HTTPException(422, document.get("readiness_detail") or "Rapor hazır değil.")
    path = document.get("download_path")
    if not path:
        raise HTTPException(422, "Bu belge için indirme yolu yok.")
    return RedirectResponse(url=path, status_code=307)


@router.get("/workflows/{workflow_id}/events", response_model=list[EyasEventOut])
def list_events(
    workflow_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    _require_eyas()
    workflow = db.get(EyasWorkflow, workflow_id)
    if not workflow:
        raise HTTPException(404, "Onay akışı bulunamadı.")
    ensure_company_access(db, user, workflow.company_id)
    return list(
        db.scalars(
            select(EyasEvent)
            .where(EyasEvent.workflow_id == workflow_id)
            .order_by(EyasEvent.id)
        ).all()
    )


def _sync_committee(db: Session, workflow: EyasWorkflow, user: User) -> None:
    if workflow.document_kind != "ohs_committee_meeting":
        return
    from app.services.committee_workflow import sync_from_eyas_transition
    sync_from_eyas_transition(db, workflow, user)


@router.post("/workflows/{workflow_id}/approve", response_model=EyasWorkflowOut)
def approve(
    workflow_id: int,
    payload: EyasDecideBody,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    _require_eyas()
    current = db.get(EyasWorkflow, workflow_id)
    if not current:
        raise HTTPException(404, "Onay akışı bulunamadı.")
    ensure_company_access(db, user, current.company_id)
    workflow = svc.decide_step(
        db,
        workflow_id=workflow_id,
        user=user,
        approve=True,
        note=payload.note,
        device_note=payload.device_note,
        ip=_client_ip(request),
        user_agent=_ua(request),
    )
    _sync_committee(db, workflow, user)
    return _wf_out(db, workflow)


@router.post("/workflows/{workflow_id}/reject", response_model=EyasWorkflowOut)
def reject(
    workflow_id: int,
    payload: EyasDecideBody,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    _require_eyas()
    current = db.get(EyasWorkflow, workflow_id)
    if not current:
        raise HTTPException(404, "Onay akışı bulunamadı.")
    ensure_company_access(db, user, current.company_id)
    workflow = svc.decide_step(
        db,
        workflow_id=workflow_id,
        user=user,
        approve=False,
        note=payload.note,
        device_note=payload.device_note,
        ip=_client_ip(request),
        user_agent=_ua(request),
    )
    _sync_committee(db, workflow, user)
    return _wf_out(db, workflow)


@router.delete("/workflows/{workflow_id}")
def delete_workflow(
    workflow_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(require_roles(*VIEW_ROLES)),
):
    _require_eyas()
    workflow = db.get(EyasWorkflow, workflow_id)
    if not workflow or not workflow.is_active:
        raise HTTPException(404, "Onay akışı bulunamadı.")
    ensure_company_access(db, user, workflow.company_id)
    if workflow.document_kind == "ohs_committee_meeting":
        raise HTTPException(409, "Kurul toplantısı onay akışı bu ekrandan silinemez; belge sürümleme kuralları uygulanmalıdır.")
    svc.soft_delete_workflow(
        db,
        workflow_id=workflow_id,
        user=user,
        ip=_client_ip(request),
        user_agent=_ua(request),
    )
    return {"ok": True, "id": workflow_id, "message": "Akış listeden kaldırıldı."}
