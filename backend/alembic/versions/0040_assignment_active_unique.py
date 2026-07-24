"""Assignment history: active-only unique (P1-06).
Revision ID: 0040
Revises: 0039
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


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("workplace_assignments"):
        return

    uqs = {u["name"] for u in insp.get_unique_constraints("workplace_assignments")}
    indexes = {i["name"]: i for i in insp.get_indexes("workplace_assignments")}

    if _OLD in uqs:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("workplace_assignments") as batch:
                batch.drop_constraint(_OLD, type_="unique")
        else:
            op.drop_constraint(_OLD, "workplace_assignments", type_="unique")

    # Eski unique index adı da olabilir
    for name, ix in list(indexes.items()):
        cols = list(ix.get("column_names") or [])
        if ix.get("unique") and cols == ["company_id", "professional_id", "professional_type"]:
            op.drop_index(name, table_name="workplace_assignments")

    insp = sa.inspect(bind)
    idx_names = {i["name"] for i in insp.get_indexes("workplace_assignments")}
    if _NEW not in idx_names:
        # Hem value ('active') hem name ('ACTIVE') etiketlerini kapsar
        where = sa.text("status IN ('active', 'ACTIVE')")
        op.create_index(
            _NEW,
            "workplace_assignments",
            ["company_id", "professional_id", "professional_type"],
            unique=True,
            postgresql_where=where,
            sqlite_where=where,
        )


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("workplace_assignments"):
        return
    idx_names = {i["name"] for i in insp.get_indexes("workplace_assignments")}
    if _NEW in idx_names:
        op.drop_index(_NEW, table_name="workplace_assignments")
    uqs = {u["name"] for u in insp.get_unique_constraints("workplace_assignments")}
    if _OLD not in uqs:
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("workplace_assignments") as batch:
                batch.create_unique_constraint(
                    _OLD, ["company_id", "professional_id", "professional_type"]
                )
        else:
            op.create_unique_constraint(
                _OLD,
                "workplace_assignments",
                ["company_id", "professional_id", "professional_type"],
            )
