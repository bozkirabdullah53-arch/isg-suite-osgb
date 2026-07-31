"""İşyeri QR doğrulama kodu + ziyaret site_verified_at.
Revision ID: 0025
Revises: 0024
"""
from typing import Sequence, Union

import secrets

import sqlalchemy as sa
from alembic import op

revision: str = "0025"
down_revision: Union[str, None] = "0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _gen_code() -> str:
    return secrets.token_urlsafe(9).replace("-", "").replace("_", "")[:12].upper()


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)

    if insp.has_table("companies"):
        cols = {c["name"] for c in insp.get_columns("companies")}
        if "site_verify_code" not in cols:
            with op.batch_alter_table("companies") as batch:
                batch.add_column(sa.Column("site_verify_code", sa.String(32), nullable=True))
            try:
                op.create_index("ix_companies_site_verify_code", "companies", ["site_verify_code"], unique=True)
            except Exception:
                pass
        rows = bind.execute(sa.text("SELECT id FROM companies WHERE site_verify_code IS NULL OR site_verify_code = ''")).fetchall()
        for (cid,) in rows:
            bind.execute(
                sa.text("UPDATE companies SET site_verify_code = :code WHERE id = :id"),
                {"code": _gen_code(), "id": cid},
            )

    if insp.has_table("service_visits"):
        cols = {c["name"] for c in insp.get_columns("service_visits")}
        with op.batch_alter_table("service_visits") as batch:
            if "site_verified_at" not in cols:
                batch.add_column(sa.Column("site_verified_at", sa.DateTime(), nullable=True))


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if insp.has_table("service_visits"):
        cols = {c["name"] for c in insp.get_columns("service_visits")}
        with op.batch_alter_table("service_visits") as batch:
            if "site_verified_at" in cols:
                batch.drop_column("site_verified_at")
    if insp.has_table("companies"):
        cols = {c["name"] for c in insp.get_columns("companies")}
        with op.batch_alter_table("companies") as batch:
            if "site_verify_code" in cols:
                batch.drop_column("site_verify_code")
