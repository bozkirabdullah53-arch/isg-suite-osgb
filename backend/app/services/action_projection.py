"""Read-only unified Action/CAPA projection over existing source domains.

This module deliberately does not migrate or rewrite RiskDof/IncidentDof or
FieldInspectionAction. Those models remain the source of truth while the shared
Action contract is introduced incrementally. Company scope is explicit and must
be resolved by the API layer through the existing authorization helpers before
calling this service.
"""
from __future__ import annotations

from datetime import date
from typing import TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import IncidentEvent, RiskAssessment
from app.models.field_inspection import FieldInspectionAction


class ActionProjectionItem(TypedDict):
    source: str
    code: str
    title: str
    action: str | None
    responsible: str | None
    term: str
    status: str
    priority: str
    parent: str
    parentSummary: str


def _iso_date(value: date | None) -> str:
    return value.isoformat() if value else ""


def incident_dof_to_action(incident: IncidentEvent, dof) -> ActionProjectionItem:
    """Normalize one incident DÖF without changing its source semantics."""
    return {
        "source": "Olay",
        "code": dof.dof_no,
        "title": dof.finding,
        "action": dof.corrective_action,
        "responsible": dof.responsible_person,
        "term": _iso_date(dof.term_date),
        "status": dof.status,
        "priority": dof.priority or "—",
        "parent": incident.form_no,
        "parentSummary": incident.short_summary,
    }


def risk_dof_to_action(risk: RiskAssessment, dof) -> ActionProjectionItem:
    """Normalize one risk DÖF without manufacturing incident-only fields."""
    return {
        "source": "Risk",
        "code": dof.dof_code,
        "title": dof.description,
        "action": dof.description,
        "responsible": dof.responsible_person,
        "term": _iso_date(dof.term_date),
        "status": "Tamamlandı" if dof.is_completed else (dof.status or "Açık"),
        "priority": "—",
        "parent": risk.risk_code,
        "parentSummary": risk.activity,
    }


def field_action_to_action(action: FieldInspectionAction) -> ActionProjectionItem:
    """Normalize a field-inspection action without rewriting its lifecycle."""
    inspection = action.inspection
    return {
        "source": "Saha",
        "code": f"SAHA-AKS-{action.id}",
        "title": action.title,
        "action": action.permanent_solution or action.activity,
        "responsible": action.responsible_person or action.responsible_role,
        "term": _iso_date(action.term_date),
        "status": action.status,
        "priority": action.priority or "—",
        "parent": inspection.inspection_no if inspection else f"DENETIM-{action.inspection_id}",
        "parentSummary": action.activity,
    }


def _incident_parent_stmt(company_ids: list[int] | None):
    stmt = (
        select(IncidentEvent)
        .options(selectinload(IncidentEvent.dofs))
        .order_by(IncidentEvent.event_date.desc())
    )
    if company_ids is not None:
        stmt = stmt.where(IncidentEvent.company_id.in_(company_ids))
    return stmt


def _risk_parent_stmt(company_ids: list[int] | None):
    stmt = (
        select(RiskAssessment)
        .options(selectinload(RiskAssessment.dofs))
        .order_by(RiskAssessment.id.desc())
    )
    if company_ids is not None:
        stmt = stmt.where(RiskAssessment.company_id.in_(company_ids))
    return stmt


def _field_action_stmt(company_ids: list[int] | None):
    stmt = (
        select(FieldInspectionAction)
        .options(selectinload(FieldInspectionAction.inspection))
        .order_by(FieldInspectionAction.id.desc())
    )
    if company_ids is not None:
        stmt = stmt.where(FieldInspectionAction.company_id.in_(company_ids))
    return stmt


def list_company_action_projection(
    db: Session,
    *,
    company_ids: list[int] | None,
    parent_limit: int = 2000,
) -> list[ActionProjectionItem]:
    """Return the current combined DÖF/action board for an authorized scope.

    `company_ids=None` is reserved for the existing global-admin unrestricted
    scope. `company_ids=[]` is deny-by-default and performs no database query.
    No source row is mutated; this is a compatibility read model only.
    """
    if company_ids == []:
        return []

    incidents = list(
        db.scalars(_incident_parent_stmt(company_ids).limit(parent_limit)).unique().all()
    )
    risks = list(
        db.scalars(_risk_parent_stmt(company_ids).limit(parent_limit)).unique().all()
    )
    field_actions = list(
        db.scalars(_field_action_stmt(company_ids).limit(parent_limit)).unique().all()
    )

    board: list[ActionProjectionItem] = []
    for incident in incidents:
        for dof in incident.dofs or []:
            board.append(incident_dof_to_action(incident, dof))
    for risk in risks:
        for dof in risk.dofs or []:
            board.append(risk_dof_to_action(risk, dof))
    for action in field_actions:
        board.append(field_action_to_action(action))
    return board
