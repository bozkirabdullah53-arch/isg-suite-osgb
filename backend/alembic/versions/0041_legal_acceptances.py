"""Legal acceptances table (P1-12).
Revision ID: 0041
Revises: 0040
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0041"
down_revision: Union[str, None] = "0040"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("legal_acceptances"):
        return
    op.create_table(
        "legal_acceptances",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id"), nullable=True),
        sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=True),
        sa.Column("document_key", sa.String(length=80), nullable=False),
        sa.Column("document_version", sa.String(length=40), nullable=False),
        sa.Column("legal_basis", sa.String(length=60), nullable=False),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=400), nullable=True),
        sa.Column("accepted_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "user_id", "document_key", "document_version", name="uq_legal_accept_user_doc_ver"
        ),
    )
    op.create_index("ix_legal_acceptances_user_id", "legal_acceptances", ["user_id"])
    op.create_index("ix_legal_acceptances_document_key", "legal_acceptances", ["document_key"])
    op.create_index("ix_legal_acceptances_accepted_at", "legal_acceptances", ["accepted_at"])
    op.create_index("ix_legal_acceptances_osgb_id", "legal_acceptances", ["osgb_id"])
    op.create_index("ix_legal_acceptances_company_id", "legal_acceptances", ["company_id"])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("legal_acceptances"):
        return
    op.drop_table("legal_acceptances")
