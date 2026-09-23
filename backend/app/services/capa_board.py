"""Company-scoped DÖF rows shared by the status center, board and export."""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import IncidentDof, IncidentEvent, RiskAssessment, RiskDof
from app.services.risk_deadlines import is_continuous_term


def incident_dof_completed(status: str | None) -> bool:
    return str(status or "").strip().casefold() in {
        "tamamlandı", "tamamlandi", "completed", "closed",
        "kapatıldı", "kapatildi", "kapalı", "kapali",
    }


def build_capa_board(db: Session, company_ids: list[int] | None) -> list[dict]:
    """Read DÖFs directly so parent-list pagination cannot hide actions."""
    if company_ids == []:
        return []
    today = date.today()
    board = []
    incident_stmt = select(IncidentDof, IncidentEvent).join(
        IncidentEvent, IncidentEvent.id == IncidentDof.incident_id
    )
    risk_stmt = select(RiskDof, RiskAssessment).join(
        RiskAssessment, RiskAssessment.id == RiskDof.risk_id
    )
    if company_ids is not None:
        incident_stmt = incident_stmt.where(IncidentEvent.company_id.in_(company_ids))
        risk_stmt = risk_stmt.where(RiskAssessment.company_id.in_(company_ids))
    for dof, incident in db.execute(incident_stmt).all():
        completed = incident_dof_completed(dof.status)
        board.append({
            "key": f"i-{dof.id}", "id": dof.id, "company_id": incident.company_id,
            "source_type": "incident", "parent_id": incident.id,
            "source": "Olay", "code": dof.dof_no, "title": dof.finding,
            "action": dof.corrective_action, "responsible": dof.responsible_person,
            "term": dof.term_date.isoformat() if dof.term_date else "",
            "status": "Tamamlandı" if completed else (dof.status or "Açık"),
            "is_completed": completed,
            "is_overdue": not completed and bool(dof.term_date and dof.term_date < today),
            "priority": dof.priority or "—", "parent": incident.form_no,
            "parentSummary": incident.short_summary,
            "root_cause": dof.root_cause, "preventive_action": dof.preventive_action,
            "completion_note": dof.effectiveness_note, "close_approval": dof.close_approval,
            "completion_date": dof.completion_date.isoformat() if dof.completion_date else "",
            "term_kind": "date" if dof.term_date else "unset", "source_term": "",
        })
    for dof, risk in db.execute(risk_stmt).all():
        completed = bool(dof.is_completed)
        board.append({
            "key": f"r-{dof.id}", "id": dof.id, "company_id": risk.company_id,
            "source_type": "risk", "parent_id": risk.id,
            "source": "Risk", "code": dof.dof_code, "title": dof.description,
            "action": dof.description, "responsible": dof.responsible_person,
            "term": dof.term_date.isoformat() if dof.term_date else "",
            "status": "Tamamlandı" if completed else (dof.status or "Açık"),
            "is_completed": completed,
            "is_overdue": not completed and bool(dof.term_date and dof.term_date < today),
            "priority": "—", "parent": risk.risk_code, "parentSummary": risk.activity,
            "responsible_department": dof.responsible_department,
            "completion_note": dof.completion_note,
            "completion_date": dof.completion_date.isoformat() if dof.completion_date else "",
            "term_kind": "date" if dof.term_date else (
                "continuous" if dof.client_reference == f"excel:{risk.source_fingerprint}:dof"
                and is_continuous_term(risk.term_text) else "unset"
            ),
            "source_term": risk.term_text if dof.client_reference == f"excel:{risk.source_fingerprint}:dof" else "",
        })
    return sorted(board, key=lambda row: (row["is_completed"], row["term"] or "9999-12-31", row["key"]))


def capa_summary(rows: list[dict]) -> dict:
    return {
        "total": len(rows),
        "open": sum(not row["is_completed"] for row in rows),
        "completed": sum(row["is_completed"] for row in rows),
        "overdue": sum(row["is_overdue"] for row in rows),
    }
