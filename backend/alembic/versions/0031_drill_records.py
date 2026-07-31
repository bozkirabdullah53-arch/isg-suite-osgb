"""Drill / tatbikat tables.
Revision ID: 0031
Revises: 0030
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0031"
down_revision: Union[str, None] = "0030"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("drill_records"):
        op.create_table(
            "drill_records",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("drill_type", sa.String(80), nullable=False),
            sa.Column("drill_date", sa.Date(), nullable=False),
            sa.Column("start_time", sa.String(10), nullable=True),
            sa.Column("end_time", sa.String(10), nullable=True),
            sa.Column("responsible", sa.String(200), nullable=True),
            sa.Column("participant_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("assembly_area", sa.String(300), nullable=True),
            sa.Column("status", sa.String(20), nullable=False, server_default="planlandi"),
            sa.Column("scenario", sa.String(10000), nullable=False),
            sa.Column("gaps", sa.String(10000), nullable=True),
            sa.Column("result", sa.String(10000), nullable=True),
            sa.Column("participants_json", sa.String(8000), nullable=True),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_drill_records_company_id", "drill_records", ["company_id"])
        op.create_index("ix_drill_records_drill_type", "drill_records", ["drill_type"])
        op.create_index("ix_drill_records_drill_date", "drill_records", ["drill_date"])
        op.create_index("ix_drill_records_status", "drill_records", ["status"])
        op.create_index("ix_drill_records_is_active", "drill_records", ["is_active"])
    if not insp.has_table("drill_photos"):
        op.create_table(
            "drill_photos",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "drill_id",
                sa.Integer(),
                sa.ForeignKey("drill_records.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("storage_path", sa.String(500), nullable=False),
            sa.Column("original_name", sa.String(255), nullable=True),
            sa.Column("content_type", sa.String(120), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_index("ix_drill_photos_drill_id", "drill_photos", ["drill_id"])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("drill_photos"):
        op.drop_table("drill_photos")
    if insp.has_table("drill_records"):
        op.drop_table("drill_records")
