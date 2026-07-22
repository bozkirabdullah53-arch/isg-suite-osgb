"""Emergency teams / support staff (acil durum ekipleri) tables.
Revision ID: 0032
Revises: 0031
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0032"
down_revision: Union[str, None] = "0031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if not insp.has_table("emergency_team_types"):
        op.create_table(
            "emergency_team_types",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True),
            sa.Column("code", sa.String(40), nullable=False),
            sa.Column("name", sa.String(120), nullable=False),
            sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("min_members", sa.Integer(), nullable=False, server_default="2"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_emergency_team_types_company_id", "emergency_team_types", ["company_id"])
        op.create_index("ix_emergency_team_types_code", "emergency_team_types", ["code"])
        op.create_index("ix_emergency_team_types_is_system", "emergency_team_types", ["is_system"])
        op.create_index("ix_emergency_team_types_is_active", "emergency_team_types", ["is_active"])

    if not insp.has_table("emergency_teams"):
        op.create_table(
            "emergency_teams",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("type_id", sa.Integer(), sa.ForeignKey("emergency_team_types.id"), nullable=False),
            sa.Column("name", sa.String(160), nullable=False),
            sa.Column("leader_assignment_id", sa.Integer(), nullable=True),
            sa.Column("min_members", sa.Integer(), nullable=False, server_default="2"),
            sa.Column("notes", sa.String(2000), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_emergency_teams_company_id", "emergency_teams", ["company_id"])
        op.create_index("ix_emergency_teams_type_id", "emergency_teams", ["type_id"])
        op.create_index("ix_emergency_teams_is_active", "emergency_teams", ["is_active"])

    if not insp.has_table("emergency_team_assignments"):
        op.create_table(
            "emergency_team_assignments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column(
                "team_id", sa.Integer(),
                sa.ForeignKey("emergency_teams.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
            sa.Column("membership", sa.String(10), nullable=False, server_default="asil"),
            sa.Column("is_leader", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("role_title", sa.String(120), nullable=True),
            sa.Column("shift", sa.String(60), nullable=True),
            sa.Column("phone", sa.String(40), nullable=True),
            sa.Column("email", sa.String(255), nullable=True),
            sa.Column("section", sa.String(120), nullable=True),
            sa.Column("personnel_no", sa.String(60), nullable=True),
            sa.Column("assign_start", sa.Date(), nullable=True),
            sa.Column("assign_end", sa.Date(), nullable=True),
            sa.Column("letter_date", sa.Date(), nullable=True),
            sa.Column("letter_no", sa.String(60), nullable=True),
            sa.Column("assigned_by", sa.String(160), nullable=True),
            sa.Column("notes", sa.String(2000), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_emergency_team_assignments_company_id", "emergency_team_assignments", ["company_id"])
        op.create_index("ix_emergency_team_assignments_team_id", "emergency_team_assignments", ["team_id"])
        op.create_index("ix_emergency_team_assignments_employee_id", "emergency_team_assignments", ["employee_id"])
        op.create_index("ix_emergency_team_assignments_membership", "emergency_team_assignments", ["membership"])
        op.create_index("ix_emergency_team_assignments_is_active", "emergency_team_assignments", ["is_active"])

    if not insp.has_table("emergency_team_trainings"):
        op.create_table(
            "emergency_team_trainings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "assignment_id", sa.Integer(),
                sa.ForeignKey("emergency_team_assignments.id", ondelete="CASCADE"), nullable=False,
            ),
            sa.Column("training_type", sa.String(120), nullable=True),
            sa.Column("provider", sa.String(160), nullable=True),
            sa.Column("trainer", sa.String(160), nullable=True),
            sa.Column("training_date", sa.Date(), nullable=True),
            sa.Column("duration_hours", sa.Float(), nullable=True),
            sa.Column("certificate_no", sa.String(80), nullable=True),
            sa.Column("valid_until", sa.Date(), nullable=True),
            sa.Column("file_path", sa.String(500), nullable=True),
            sa.Column("first_aid_cert_no", sa.String(80), nullable=True),
            sa.Column("first_aid_center", sa.String(160), nullable=True),
            sa.Column("first_aid_start", sa.Date(), nullable=True),
            sa.Column("first_aid_end", sa.Date(), nullable=True),
            sa.Column("refresh_date", sa.Date(), nullable=True),
            sa.Column("notes", sa.String(2000), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_emergency_team_trainings_assignment_id", "emergency_team_trainings", ["assignment_id"])
        op.create_index("ix_emergency_team_trainings_valid_until", "emergency_team_trainings", ["valid_until"])

    if not insp.has_table("emergency_sufficiency_rules"):
        op.create_table(
            "emergency_sufficiency_rules",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("hazard_class", sa.String(40), nullable=True),
            sa.Column("team_code", sa.String(40), nullable=True),
            sa.Column("min_members", sa.Integer(), nullable=False, server_default="2"),
            sa.Column("min_per_shift", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("notes", sa.String(1000), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        )
        op.create_index("ix_emergency_sufficiency_rules_hazard_class", "emergency_sufficiency_rules", ["hazard_class"])
        op.create_index("ix_emergency_sufficiency_rules_team_code", "emergency_sufficiency_rules", ["team_code"])
        op.create_index("ix_emergency_sufficiency_rules_is_active", "emergency_sufficiency_rules", ["is_active"])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for table in (
        "emergency_team_trainings",
        "emergency_team_assignments",
        "emergency_teams",
        "emergency_sufficiency_rules",
        "emergency_team_types",
    ):
        if insp.has_table(table):
            op.drop_table(table)
