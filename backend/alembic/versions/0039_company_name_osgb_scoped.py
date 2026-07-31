"""Company.name unique → (osgb_id, name) scoped (P1-05).
Revision ID: 0039
Revises: 0038
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0039"
down_revision: Union[str, None] = "0038"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("companies"):
        return

    dialect = bind.dialect.name
    uqs = {u["name"]: u for u in insp.get_unique_constraints("companies")}
    indexes = {i["name"]: i for i in insp.get_indexes("companies")}

    def _is_name_only(cols) -> bool:
        return list(cols or []) == ["name"]

    # Drop global unique on companies.name (constraint and/or unique index)
    for name, uq in list(uqs.items()):
        if _is_name_only(uq.get("column_names")):
            if dialect == "sqlite":
                with op.batch_alter_table("companies") as batch:
                    batch.drop_constraint(name, type_="unique")
            else:
                op.drop_constraint(name, "companies", type_="unique")

    insp = sa.inspect(bind)
    indexes = {i["name"]: i for i in insp.get_indexes("companies")}
    for name, ix in list(indexes.items()):
        if ix.get("unique") and _is_name_only(ix.get("column_names")):
            op.drop_index(name, table_name="companies")

    # Non-unique search index on name
    insp = sa.inspect(bind)
    indexes = {i["name"] for i in insp.get_indexes("companies")}
    if "ix_companies_name" not in indexes:
        op.create_index("ix_companies_name", "companies", ["name"], unique=False)

    insp = sa.inspect(bind)
    uq_names = {u["name"] for u in insp.get_unique_constraints("companies")}
    idx_names = {i["name"] for i in insp.get_indexes("companies")}
    if "uq_company_osgb_name" not in uq_names and "uq_company_osgb_name" not in idx_names:
        if dialect == "sqlite":
            with op.batch_alter_table("companies") as batch:
                batch.create_unique_constraint("uq_company_osgb_name", ["osgb_id", "name"])
        else:
            op.create_unique_constraint("uq_company_osgb_name", "companies", ["osgb_id", "name"])


def downgrade():
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if not insp.has_table("companies"):
        return
    dialect = bind.dialect.name
    uq_names = {u["name"] for u in insp.get_unique_constraints("companies")}
    if "uq_company_osgb_name" in uq_names:
        if dialect == "sqlite":
            with op.batch_alter_table("companies") as batch:
                batch.drop_constraint("uq_company_osgb_name", type_="unique")
        else:
            op.drop_constraint("uq_company_osgb_name", "companies", type_="unique")
    # Restore global unique — may fail if cross-tenant same names exist
    insp = sa.inspect(bind)
    indexes = {i["name"]: i for i in insp.get_indexes("companies")}
    if "ix_companies_name" in indexes and not indexes["ix_companies_name"].get("unique"):
        op.drop_index("ix_companies_name", table_name="companies")
    op.create_index("ix_companies_name", "companies", ["name"], unique=True)
