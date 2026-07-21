"""Chemical product SDS register.
Revision ID: 0027
Revises: 0026
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0027"
down_revision: Union[str, None] = "0026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("chemical_products"):
        return
    # No inline ForeignKey() — avoids SQLAlchemy f405 on Render alembic runs.
    op.create_table(
        "chemical_products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("company_id", sa.Integer(), nullable=False),
        sa.Column("branch_id", sa.Integer(), nullable=True),
        sa.Column("product_name", sa.String(220), nullable=False),
        sa.Column("cas_number", sa.String(40), nullable=True),
        sa.Column("has_sds_file", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=True),
        sa.Column("next_review_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.String(1000), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_by_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_chemical_products_company_id", "chemical_products", ["company_id"])
    op.create_index("ix_chemical_products_product_name", "chemical_products", ["product_name"])
    op.create_index("ix_chemical_products_next_review_date", "chemical_products", ["next_review_date"])
    op.create_index("ix_chemical_products_document_id", "chemical_products", ["document_id"])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("chemical_products"):
        op.drop_table("chemical_products")
