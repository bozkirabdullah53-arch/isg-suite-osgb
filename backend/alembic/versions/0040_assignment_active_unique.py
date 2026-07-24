"""Assignment history: active-only unique (P1-06).
Revision ID: 0040
Revises: 0039

Prod notu: PG'de UniqueConstraint hem constraint hem index olarak görünür;
önce DROP CONSTRAINT, sonra aynı isme DROP INDEX → "index does not exist".
Bu sürüm IF EXISTS + yeniden inspect ile idempotent.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0040"
down_revision: Union[str, None] = "0039"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD = "uq_company_professional_assignment"
_NEW = "uq_assignment_active_company_pro_type"
_TARGET_COLS = ("company_id", "professional_id", "professional_type")


def _quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def _drop_unique_constraint(bind, table: str, name: str) -> None:
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(name, type_="unique")
        return
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                f"ALTER TABLE {_quote_ident(table)} "
                f"DROP CONSTRAINT IF EXISTS {_quote_ident(name)}"
            )
        )
        return
    op.drop_constraint(name, table, type_="unique")


def _drop_index_if_exists(bind, table: str, name: str) -> None:
    if bind.dialect.name == "postgresql":
        # Unique constraint index'i constraint ile birlikte gitmiş olabilir
        op.execute(sa.text(f"DROP INDEX IF EXISTS {_quote_ident(name)}"))
        return
    if bind.dialect.name == "sqlite":
        op.execute(sa.text(f"DROP INDEX IF EXISTS {_quote_ident(name)}"))
        return
    op.drop_index(name, table_name=table)


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("workplace_assignments"):
        return

    uqs = {u["name"] for u in insp.get_unique_constraints("workplace_assignments") if u.get("name")}
    # 1) İsimli eski unique constraint
    if _OLD in uqs:
        _drop_unique_constraint(bind, "workplace_assignments", _OLD)

    # 2) Aynı kolonlardaki diğer unique constraint'ler (isim farkı)
    insp = sa.inspect(bind)
    for uq in insp.get_unique_constraints("workplace_assignments"):
        name = uq.get("name")
        cols = tuple(uq.get("column_names") or ())
        if name and cols == _TARGET_COLS:
            _drop_unique_constraint(bind, "workplace_assignments", name)

    # 3) Kalan unique index'ler (yeniden inspect — constraint sonrası stale liste yok)
    insp = sa.inspect(bind)
    for ix in insp.get_indexes("workplace_assignments"):
        name = ix.get("name")
        cols = tuple(ix.get("column_names") or ())
        if not name or not ix.get("unique") or cols != _TARGET_COLS:
            continue
        if name == _NEW:
            continue
        _drop_index_if_exists(bind, "workplace_assignments", name)

    # 4) Active-only partial unique
    insp = sa.inspect(bind)
    idx_names = {i["name"] for i in insp.get_indexes("workplace_assignments") if i.get("name")}
    uq_names = {u["name"] for u in insp.get_unique_constraints("workplace_assignments") if u.get("name")}
    if _NEW not in idx_names and _NEW not in uq_names:
        if bind.dialect.name == "postgresql":
            where = sa.text("status = 'ACTIVE'")
        else:
            where = sa.text("status IN ('active', 'ACTIVE')")
        op.create_index(
            _NEW,
            "workplace_assignments",
            list(_TARGET_COLS),
            unique=True,
            postgresql_where=where if bind.dialect.name == "postgresql" else None,
            sqlite_where=where if bind.dialect.name == "sqlite" else None,
        )


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("workplace_assignments"):
        return
    idx_names = {i["name"] for i in insp.get_indexes("workplace_assignments") if i.get("name")}
    if _NEW in idx_names:
        _drop_index_if_exists(bind, "workplace_assignments", _NEW)
    uqs = {u["name"] for u in insp.get_unique_constraints("workplace_assignments") if u.get("name")}
    if _OLD not in uqs:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("workplace_assignments") as batch:
                batch.create_unique_constraint(
                    _OLD, list(_TARGET_COLS)
                )
        else:
            op.create_unique_constraint(
                _OLD,
                "workplace_assignments",
                list(_TARGET_COLS),
            )
