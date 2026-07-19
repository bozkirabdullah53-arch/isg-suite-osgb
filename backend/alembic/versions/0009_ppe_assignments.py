"""KKD zimmet tables.
Revision ID: 0009
Revises: 0008
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("ppe_assignments"):
        return
    op.create_table(
        "ppe_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("employee_id", sa.Integer(), nullable=False),
        sa.Column("delivery_date", sa.Date(), nullable=False),
        sa.Column("category", sa.String(120), nullable=False),
        sa.Column("item_type", sa.String(160), nullable=False),
        sa.Column("quantity", sa.Integer(), server_default="1"),
        sa.Column("brand", sa.String(120), nullable=True),
        sa.Column("model", sa.String(120), nullable=True),
        sa.Column("size", sa.String(60), nullable=True),
        sa.Column("serial_no", sa.String(120), nullable=True),
        sa.Column("shelf_life_text", sa.String(120), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("warranty_text", sa.String(120), nullable=True),
        sa.Column("renewal_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(40), server_default="teslim"),
        sa.Column("delivered_by", sa.String(160), nullable=True),
        sa.Column("risk_note", sa.String(1000), nullable=True),
        sa.Column("notes", sa.String(2000), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_ppe_assignments_company_id", "ppe_assignments", ["company_id"])
    op.create_index("ix_ppe_assignments_employee_id", "ppe_assignments", ["employee_id"])
    op.create_index("ix_ppe_assignments_status", "ppe_assignments", ["status"])
    op.create_index("ix_ppe_assignments_renewal_date", "ppe_assignments", ["renewal_date"])

    op.create_table(
        "ppe_assignment_photos",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("assignment_id", sa.Integer(), nullable=False),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("original_name", sa.String(255), nullable=True),
        sa.Column("content_type", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_ppe_assignment_photos_assignment_id", "ppe_assignment_photos", ["assignment_id"])


def downgrade():
    op.drop_table("ppe_assignment_photos")
    op.drop_table("ppe_assignments")
