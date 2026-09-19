"""Add tenant-scoped, read-only employer access to health tracking.

Revision ID: 0115_health_employer_read
Revises: 0114_email_inbox_attachments
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0115_health_employer_read"
down_revision: Union[str, None] = "0114_email_inbox_attachments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_EMPLOYER_SCOPE = """
  COALESCE(current_setting('app.health_employer_access', true), '') = '1'
  AND company_id = ANY (
    string_to_array(
      COALESCE(NULLIF(current_setting('app.allowed_company_ids', true), ''), '-1'), ','
    )::integer[]
  )
"""


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    inspector = sa.inspect(bind)
    required = {"health_records", "health_access_logs"}
    if not all(inspector.has_table(table) for table in required):
        return

    # Mevcut klinik FOR ALL policy korunur. Bu ek policy yalnız SELECT verir;
    # işyeri hesabı health_records üzerinde INSERT/UPDATE/DELETE policy'si almaz.
    op.execute(sa.text(
        "DROP POLICY IF EXISTS health_records_employer_read_scope ON health_records"
    ))
    op.execute(sa.text(
        "CREATE POLICY health_records_employer_read_scope ON health_records "
        f"FOR SELECT USING ({_EMPLOYER_SCOPE})"
    ))

    # Okuma/indirme olayı hash zincirine eklenirken önceki hash okunur ve yeni
    # olay eklenir. UPDATE/DELETE append-only trigger ve policy ile kapalı kalır.
    op.execute(sa.text(
        "DROP POLICY IF EXISTS health_access_logs_employer_chain_read_scope "
        "ON health_access_logs"
    ))
    op.execute(sa.text(
        "CREATE POLICY health_access_logs_employer_chain_read_scope "
        "ON health_access_logs FOR SELECT "
        f"USING ({_EMPLOYER_SCOPE})"
    ))
    op.execute(sa.text(
        "DROP POLICY IF EXISTS health_access_logs_employer_append_scope "
        "ON health_access_logs"
    ))
    op.execute(sa.text(
        "CREATE POLICY health_access_logs_employer_append_scope "
        "ON health_access_logs FOR INSERT "
        f"WITH CHECK ({_EMPLOYER_SCOPE})"
    ))


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    inspector = sa.inspect(bind)
    if inspector.has_table("health_access_logs"):
        op.execute(sa.text(
            "DROP POLICY IF EXISTS health_access_logs_employer_append_scope "
            "ON health_access_logs"
        ))
        op.execute(sa.text(
            "DROP POLICY IF EXISTS health_access_logs_employer_chain_read_scope "
            "ON health_access_logs"
        ))
    if inspector.has_table("health_records"):
        op.execute(sa.text(
            "DROP POLICY IF EXISTS health_records_employer_read_scope ON health_records"
        ))
