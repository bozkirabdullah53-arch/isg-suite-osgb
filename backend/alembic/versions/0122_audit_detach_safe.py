"""Audit chain: FK-detach-safe guard, FK-independent canonical hash, chain verify.

0121 made ``audit_logs`` strictly append-only with a PostgreSQL trigger, but the
application still performs FK-detach maintenance updates when a user or company
is permanently deleted (``users._detach_user_refs``, ``companies._purge_company_data``).
After 0121 those updates would raise in production and break the delete flows.

This revision keeps audit_logs append-only for all content while explicitly
allowing the narrow FK-detach maintenance update (``user_id``/``company_id``
-> NULL, every hashed column untouched). Because detached FK columns are no
longer part of the record identity, the canonical hash is rebuilt WITHOUT
user_id/company_id so chain verification stays sound across detachment.

Also creates ``audit_chain_verify()`` — a set-based integrity checker used by
``GET /api/v1/security/audit-chain``.

Revision ID: 0122
Revises: 0121
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0122"
down_revision: Union[str, None] = "0121"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_CANONICAL_0122 = """concat_ws('|',
    coalesce({p}id::text, ''),
    coalesce({p}action, ''),
    coalesce({p}entity_type, ''),
    coalesce({p}entity_id, ''),
    coalesce({p}description, ''),
    coalesce({p}ip_address, ''),
    coalesce({p}module, ''),
    coalesce({p}old_value, ''),
    coalesce({p}new_value, ''),
    coalesce({p}created_at::text, ''),
    coalesce(previous_hash, '')
)"""

_CANONICAL_0121 = """concat_ws('|',
    coalesce({p}id::text, ''),
    coalesce({p}user_id::text, ''),
    coalesce({p}company_id::text, ''),
    coalesce({p}action, ''),
    coalesce({p}entity_type, ''),
    coalesce({p}entity_id, ''),
    coalesce({p}description, ''),
    coalesce({p}ip_address, ''),
    coalesce({p}module, ''),
    coalesce({p}old_value, ''),
    coalesce({p}new_value, ''),
    coalesce({p}created_at::text, ''),
    coalesce(previous_hash, '')
)"""


def _rebuild_chain(canonical_expr: str) -> str:
    return (
        """
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
                canonical := """
        + canonical_expr.format(p="r.")
        + """;
                UPDATE audit_logs
                   SET prev_hash = previous_hash,
                       event_hash = encode(digest(canonical, 'sha256'), 'hex')
                 WHERE id = r.id;
                SELECT encode(digest(canonical, 'sha256'), 'hex') INTO previous_hash;
            END LOOP;
        END $$;
        """
    )


def _install_0122_functions() -> None:
    # Hash-on-insert: canonical EXCLUDES user_id/company_id (detach-safe identity).
    op.execute(sa.text(
        """
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
            canonical := """
        + _CANONICAL_0122.format(p="NEW.")
        + """;
            NEW.event_hash := encode(digest(canonical, 'sha256'), 'hex');
            RETURN NEW;
        END;
        $$;
        """
    ))
    # Append-only guard with the single narrow exception: FK detach maintenance.
    op.execute(sa.text(
        """
        CREATE OR REPLACE FUNCTION audit_logs_append_only_guard()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            IF TG_OP = 'DELETE' THEN
                RAISE EXCEPTION 'audit_logs is append-only: DELETE is forbidden';
            END IF;

            IF (NEW.user_id IS NULL OR NEW.user_id = OLD.user_id)
               AND (NEW.company_id IS NULL OR NEW.company_id = OLD.company_id)
               AND (NEW.user_id IS DISTINCT FROM OLD.user_id
                    OR NEW.company_id IS DISTINCT FROM OLD.company_id)
               AND NEW.id = OLD.id
               AND NEW.action IS NOT DISTINCT FROM OLD.action
               AND NEW.entity_type IS NOT DISTINCT FROM OLD.entity_type
               AND NEW.entity_id IS NOT DISTINCT FROM OLD.entity_id
               AND NEW.description IS NOT DISTINCT FROM OLD.description
               AND NEW.ip_address IS NOT DISTINCT FROM OLD.ip_address
               AND NEW.module IS NOT DISTINCT FROM OLD.module
               AND NEW.old_value IS NOT DISTINCT FROM OLD.old_value
               AND NEW.new_value IS NOT DISTINCT FROM OLD.new_value
               AND NEW.created_at IS NOT DISTINCT FROM OLD.created_at
               AND NEW.prev_hash IS NOT DISTINCT FROM OLD.prev_hash
               AND NEW.event_hash IS NOT DISTINCT FROM OLD.event_hash
            THEN
                RETURN NEW;
            END IF;

            RAISE EXCEPTION
              'audit_logs is append-only: only FK detach (user_id/company_id -> NULL) updates are permitted';
        END;
        $$;
        """
    ))
    # Set-based integrity checker (chain order + per-row content hash).
    op.execute(sa.text(
        """
        CREATE OR REPLACE FUNCTION audit_chain_verify()
        RETURNS TABLE(total bigint, chain_breaks bigint, hash_breaks bigint)
        LANGUAGE sql
        STABLE
        AS $$
            WITH ordered AS (
                SELECT
                    id,
                    event_hash,
                    prev_hash,
                    lag(event_hash) OVER (ORDER BY id) AS expected_prev,
                    encode(digest(concat_ws('|',
                        coalesce(id::text, ''),
                        coalesce(action, ''),
                        coalesce(entity_type, ''),
                        coalesce(entity_id, ''),
                        coalesce(description, ''),
                        coalesce(ip_address, ''),
                        coalesce(module, ''),
                        coalesce(old_value, ''),
                        coalesce(new_value, ''),
                        coalesce(created_at::text, ''),
                        coalesce(prev_hash, '')
                    ), 'sha256'), 'hex') AS expected_hash
                FROM audit_logs
            )
            SELECT
                count(*),
                count(*) FILTER (WHERE prev_hash IS DISTINCT FROM expected_prev),
                count(*) FILTER (WHERE event_hash IS DISTINCT FROM expected_hash)
            FROM ordered;
        $$;
        """
    ))


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "audit_logs" not in inspector.get_table_names():
        return
    if bind.dialect.name != "postgresql":
        # SQLite dev/test: columns already exist via 0121; triggers are PG-only.
        return

    # Drop both triggers so the rebuild can rewrite hashes in place.
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_audit_logs_hash_on_insert ON audit_logs"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_audit_logs_append_only_guard ON audit_logs"))

    _install_0122_functions()

    # Rebuild the whole chain with the FK-independent canonical definition.
    op.execute(sa.text(_rebuild_chain(_CANONICAL_0122)))

    op.execute(sa.text(
        """
        CREATE TRIGGER trg_audit_logs_hash_on_insert
        BEFORE INSERT ON audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION audit_logs_hash_on_insert();
        """
    ))
    op.execute(sa.text(
        """
        CREATE TRIGGER trg_audit_logs_append_only_guard
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION audit_logs_append_only_guard();
        """
    ))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "audit_logs" not in inspector.get_table_names():
        return
    if bind.dialect.name != "postgresql":
        return

    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_audit_logs_hash_on_insert ON audit_logs"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS trg_audit_logs_append_only_guard ON audit_logs"))
    op.execute(sa.text("DROP FUNCTION IF EXISTS audit_chain_verify()"))

    # Restore strict 0121 semantics (canonical includes FK ids, guard rejects all).
    op.execute(sa.text(
        """
        CREATE OR REPLACE FUNCTION audit_logs_hash_on_insert()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        DECLARE
            previous_hash TEXT;
            canonical TEXT;
        BEGIN
            PERFORM pg_advisory_xact_lock(hashtext('isgsuite.audit_logs.chain'));
            SELECT event_hash INTO previous_hash FROM audit_logs ORDER BY id DESC LIMIT 1;
            NEW.prev_hash := previous_hash;
            canonical := """
        + _CANONICAL_0121.format(p="NEW.")
        + """;
            NEW.event_hash := encode(digest(canonical, 'sha256'), 'hex');
            RETURN NEW;
        END;
        $$;
        """
    ))
    op.execute(sa.text(
        """
        CREATE OR REPLACE FUNCTION audit_logs_append_only_guard()
        RETURNS trigger
        LANGUAGE plpgsql
        AS $$
        BEGIN
            RAISE EXCEPTION 'audit_logs is append-only: UPDATE/DELETE is forbidden';
        END;
        $$;
        """
    ))
    op.execute(sa.text(_rebuild_chain(_CANONICAL_0121)))
    op.execute(sa.text(
        """
        CREATE TRIGGER trg_audit_logs_hash_on_insert
        BEFORE INSERT ON audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION audit_logs_hash_on_insert();
        """
    ))
    op.execute(sa.text(
        """
        CREATE TRIGGER trg_audit_logs_append_only_guard
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW
        EXECUTE FUNCTION audit_logs_append_only_guard();
        """
    ))
