"""Make audit_logs append-only and tamper-evident.

Revision ID: 0121
Revises: 0120_pkd_register
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0121"
down_revision: Union[str, None] = "0120_pkd_register"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "audit_logs" not in inspector.get_table_names():
        return
    if bind.dialect.name != "postgresql":
        # SQLite test/dev databases remain compatible; production is PostgreSQL.
        cols = {c["name"] for c in inspector.get_columns("audit_logs")}
        with op.batch_alter_table("audit_logs") as batch:
            if "prev_hash" not in cols:
                batch.add_column(sa.Column("prev_hash", sa.String(64), nullable=True))
            if "event_hash" not in cols:
                batch.add_column(sa.Column("event_hash", sa.String(64), nullable=True))
        return

    op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))

    cols = {c["name"] for c in inspector.get_columns("audit_logs")}
    if "prev_hash" not in cols:
        op.add_column("audit_logs", sa.Column("prev_hash", sa.String(64), nullable=True))
    if "event_hash" not in cols:
        op.add_column("audit_logs", sa.Column("event_hash", sa.String(64), nullable=True))

    # Backfill the existing history once, in immutable id order.
    op.execute(sa.text("""
        DO $$
        DECLARE
            r RECORD;
            previous_hash TEXT := NULL;
            canonical TEXT;
        BEGIN
            FOR r IN
                SELECT id, user_id, company_id, action, entity_type, entity_id,
                       description, ip_address, module, old_value, new_value, created_at
                FROM audit_logs
                ORDER BY id
            LOOP
                canonical := concat_ws('|',
                    coalesce(r.id::text, ''),
                    coalesce(r.user_id::text, ''),
                    coalesce(r.company_id::text, ''),
                    coalesce(r.action, ''),
                    coalesce(r.entity_type, ''),
                    coalesce(r.entity_id, ''),
                    coalesce(r.description, ''),
                    coalesce(r.ip_address, ''),
                    coalesce(r.module, ''),
                    coalesce(r.old_value, ''),
                    coalesce(r.new_value, ''),
                    coalesce(r.created_at::text, ''),
                    coalesce(previous_hash, '')
                );
                UPDATE audit_logs
                   SET prev_hash = previous_hash,
                       event_hash = encode(digest(canonical, 'sha256'), 'hex')
                 WHERE id = r.id;
                SELECT encode(digest(canonical, 'sha256'), 'hex') INTO previous_hash;
            END LOOP;
        END $$;
    """))

    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION audit_logs_append_only_guard()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only: UPDATE/DELETE is forbidden';
        END;
        $$;
    """))

    op.execute(sa.text("""
        CREATE OR REPLACE FUNCTION audit_logs_hash_on_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            previous_hash TEXT;
            canonical TEXT;
        BEGIN
            PERFORM pg_advisory_xact_lock(hashtext('isgsuite.audit_logs.chain'));

            SELECT event_hash
              INTO previous_hash
              FROM audit_logs
             ORDER BY id DESC
             LIMIT 1;

            NEW.prev_hash := previous_hash;
            canonical := concat_ws('|',
                coalesce(NEW.id::text, ''),
                coalesce(NEW.user_id::text, ''),
                coalesce(NEW.company_id::text, ''),
                coalesce(NEW.action, ''),
                coalesce(NEW.entity_type, ''),
                coalesce(NEW.entity_id, ''),
                coalesce(NEW.description, ''),
                coalesce(NEW.ip_address, ''),
                coalesce(NEW.module, ''),
                coalesce(NEW.old_value, ''),
                coalesce(NEW.new_value, ''),
                coalesce(NEW.created_at::text, ''),
                coalesce(previous_hash, '')
            );
            NEW.event_hash := encode(digest(canonical, 'sha256'), 'hex');
            RETURN NEW;
        END;
        $$;
    """))

    op.execute(sa.text("""
        DROP TRIGGER IF EXISTS trg_audit_logs_hash_on_insert ON audit_logs;
        CREATE TRIGGER trg_audit_logs_hash_on_insert
        BEFORE INSERT ON audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION audit_logs_hash_on_insert();
    """))

    op.execute(sa.text("""
        DROP TRIGGER IF EXISTS trg_audit_logs_append_only_guard ON audit_logs;
        CREATE TRIGGER trg_audit_logs_append_only_guard
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION audit_logs_append_only_guard();
    """))

    op.execute(sa.text("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_audit_logs_event_hash
        ON audit_logs(event_hash)
    """))
    op.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS ix_audit_logs_prev_hash
        ON audit_logs(prev_hash)
    """))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "audit_logs" not in inspector.get_table_names():
        return
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP TRIGGER IF EXISTS trg_audit_logs_hash_on_insert ON audit_logs"))
        op.execute(sa.text("DROP TRIGGER IF EXISTS trg_audit_logs_append_only_guard ON audit_logs"))
        op.execute(sa.text("DROP FUNCTION IF EXISTS audit_logs_hash_on_insert()"))
        op.execute(sa.text("DROP FUNCTION IF EXISTS audit_logs_append_only_guard()"))
        op.execute(sa.text("DROP INDEX IF EXISTS uq_audit_logs_event_hash"))
        op.execute(sa.text("DROP INDEX IF EXISTS ix_audit_logs_prev_hash"))
    cols = {c["name"] for c in inspector.get_columns("audit_logs")}
    with op.batch_alter_table("audit_logs") as batch:
        if "event_hash" in cols:
            batch.drop_column("event_hash")
        if "prev_hash" in cols:
            batch.drop_column("prev_hash")
