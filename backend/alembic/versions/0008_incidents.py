"""Incident events tables.
Revision ID: 0008
Revises: 0007
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("incident_events"):
        return
    # No inline ForeignKey() — avoids SQLAlchemy f405 on Render alembic runs.
    op.create_table(
        "incident_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("form_no", sa.String(40), nullable=False),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(40), server_default="Aktif"),
        sa.Column("recorded_by_name", sa.String(160), nullable=True),
        sa.Column("safety_specialist", sa.String(160), nullable=True),
        sa.Column("workplace_physician", sa.String(160), nullable=True),
        sa.Column("employer_representative", sa.String(160), nullable=True),
        sa.Column("department", sa.String(160), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("event_time", sa.String(10), nullable=True),
        sa.Column("location", sa.String(220), nullable=True),
        sa.Column("area", sa.String(160), nullable=True),
        sa.Column("work_being_done", sa.String(500), nullable=True),
        sa.Column("related_people", sa.String(2000), nullable=True),
        sa.Column("has_witness", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("witness_names", sa.String(2000), nullable=True),
        sa.Column("equipment_used", sa.String(500), nullable=True),
        sa.Column("chemical_used", sa.String(500), nullable=True),
        sa.Column("short_summary", sa.String(500), nullable=False),
        sa.Column("detail", sa.String(4000), nullable=True),
        sa.Column("classification", sa.String(160), nullable=True),
        sa.Column("injury_occurred", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("health_complaint", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("medical_intervention", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("work_incapacity_report", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("equipment_damage", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("would_have_injured", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("auto_warning", sa.String(2000), nullable=True),
        sa.Column("probability", sa.Integer(), server_default="0"),
        sa.Column("severity", sa.Integer(), server_default="0"),
        sa.Column("risk_score", sa.Integer(), server_default="0"),
        sa.Column("risk_level", sa.String(40), nullable=True),
        sa.Column("risk_analysis_status", sa.String(50), nullable=True),
        sa.Column("risk_analysis_note", sa.String(2000), nullable=True),
        sa.Column("emergency_relation", sa.String(160), nullable=True),
        sa.Column("emergency_note", sa.String(2000), nullable=True),
        sa.Column("evaluation_text", sa.String(4000), nullable=True),
        sa.Column("sgk_reported", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("sgk_report_date", sa.Date(), nullable=True),
        sa.Column("police_reported", sa.Boolean(), server_default=sa.text("false")),
        sa.Column("accident_type", sa.String(120), nullable=True),
        sa.Column("injury_type", sa.String(220), nullable=True),
        sa.Column("intervention_detail", sa.String(2000), nullable=True),
        sa.Column("report_days", sa.Integer(), server_default="0"),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_incident_events_form_no", "incident_events", ["form_no"], unique=True)
    op.create_index("ix_incident_events_company_id", "incident_events", ["company_id"])
    op.create_index("ix_incident_events_event_type", "incident_events", ["event_type"])

    op.create_table(
        "incident_root_causes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("why_1", sa.String(2000), nullable=True),
        sa.Column("why_2", sa.String(2000), nullable=True),
        sa.Column("why_3", sa.String(2000), nullable=True),
        sa.Column("why_4", sa.String(2000), nullable=True),
        sa.Column("why_5", sa.String(2000), nullable=True),
        sa.Column("root_cause", sa.String(2000), nullable=True),
        sa.Column("root_cause_category", sa.String(160), nullable=True),
        sa.Column("systemic_gap", sa.String(2000), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_incident_root_causes_incident_id", "incident_root_causes", ["incident_id"], unique=True)

    op.create_table(
        "incident_dofs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dof_no", sa.String(40), nullable=False),
        sa.Column("incident_id", sa.Integer(), nullable=False),
        sa.Column("finding", sa.String(2000), nullable=False),
        sa.Column("root_cause", sa.String(2000), nullable=True),
        sa.Column("corrective_action", sa.String(2000), nullable=True),
        sa.Column("preventive_action", sa.String(2000), nullable=True),
        sa.Column("responsible_person", sa.String(160), nullable=True),
        sa.Column("term_date", sa.Date(), nullable=True),
        sa.Column("priority", sa.String(30), server_default="Orta"),
        sa.Column("status", sa.String(40), server_default="Açık"),
        sa.Column("completion_date", sa.Date(), nullable=True),
        sa.Column("effectiveness_note", sa.String(2000), nullable=True),
        sa.Column("close_approval", sa.String(160), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_incident_dofs_dof_no", "incident_dofs", ["dof_no"], unique=True)
    op.create_index("ix_incident_dofs_incident_id", "incident_dofs", ["incident_id"])


def downgrade():
    op.drop_table("incident_dofs")
    op.drop_table("incident_root_causes")
    op.drop_table("incident_events")
