"""Revision ID: 0019
Revises: 0018
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("eisa_archive_records"):
        return
    op.create_table(
        "eisa_archive_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id"), nullable=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("entity_type", sa.String(80), nullable=True),
        sa.Column("entity_id", sa.String(80), nullable=True),
        sa.Column("original_name", sa.String(255), nullable=True),
        sa.Column("storage_path", sa.String(500), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("checksum", sa.String(64), nullable=True),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_eisa_archive_records_kind", "eisa_archive_records", ["kind"])
    op.create_index("ix_eisa_archive_records_osgb_id", "eisa_archive_records", ["osgb_id"])
    op.create_index("ix_eisa_archive_records_created_at", "eisa_archive_records", ["created_at"])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("eisa_archive_records"):
        op.drop_table("eisa_archive_records")
