"""Reconcile employee national-id uniqueness with company scope.

Revision ID: 0100_employee_national_scope
Revises: 0099_education_audit
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0100_employee_national_scope"
down_revision: Union[str, None] = "0099_education_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "employees" not in set(inspector.get_table_names()):
        return

    # Eski kurulumlarda TC kimlik tüm firmalar için tekil bırakılmıştı.
    # Güncel veri modeli tekilliği firma + TC kimlik kapsamında uygular.
    for constraint in inspector.get_unique_constraints("employees"):
        columns = list(constraint.get("column_names") or [])
        name = constraint.get("name")
        if columns == ["national_id_masked"] and name:
            with op.batch_alter_table("employees") as batch:
                batch.drop_constraint(name, type_="unique")

    inspector = sa.inspect(bind)
    for index in inspector.get_indexes("employees"):
        columns = list(index.get("column_names") or [])
        name = index.get("name")
        if index.get("unique") and columns == ["national_id_masked"] and name:
            op.drop_index(name, table_name="employees")

    inspector = sa.inspect(bind)
    has_company_scope = any(
        list(constraint.get("column_names") or []) == ["company_id", "national_id_masked"]
        for constraint in inspector.get_unique_constraints("employees")
    )
    if not has_company_scope:
        with op.batch_alter_table("employees") as batch:
            batch.create_unique_constraint(
                "uq_employee_company_national",
                ["company_id", "national_id_masked"],
            )


def downgrade() -> None:
    # Firma bazlı doğru tekillik korunur. Global TC tekilliğine dönüş veri kaybı
    # veya mevcut kayıtların çakışmasına yol açabileceği için uygulanmaz.
    pass
