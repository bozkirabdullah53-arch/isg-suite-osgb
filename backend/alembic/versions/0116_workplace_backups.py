"""add workplace backup execution metadata

Revision ID: 0116_workplace_backups
Revises: 0115_health_employer_read
"""
from alembic import op
import sqlalchemy as sa

revision = "0116_workplace_backups"
down_revision = "0115_health_employer_read"
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {column["name"] for column in inspector.get_columns("eisa_archive_records")}
    columns = (
        ("backup_source", sa.String(20), False, "manual"),
        ("backup_status", sa.String(20), False, "completed"),
        ("started_at", sa.DateTime(), True, None),
        ("completed_at", sa.DateTime(), True, None),
        ("error_summary", sa.String(1000), True, None),
        ("schedule_key", sa.String(120), True, None),
    )
    for name, type_, nullable, server_default in columns:
        if name in existing_columns:
            continue
        op.add_column(
            "eisa_archive_records",
            sa.Column(
                name,
                type_,
                nullable=nullable,
                server_default=server_default,
            ),
        )

    constraint_names = {
        constraint.get("name")
        for constraint in inspector.get_unique_constraints("eisa_archive_records")
    }
    if "uq_eisa_archive_records_schedule_key" not in constraint_names:
        op.create_unique_constraint(
            "uq_eisa_archive_records_schedule_key",
            "eisa_archive_records",
            ["schedule_key"],
        )

def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    constraint_names = {
        constraint.get("name")
        for constraint in inspector.get_unique_constraints("eisa_archive_records")
    }
    if "uq_eisa_archive_records_schedule_key" in constraint_names:
        op.drop_constraint("uq_eisa_archive_records_schedule_key", "eisa_archive_records", type_="unique")

    existing_columns = {column["name"] for column in inspector.get_columns("eisa_archive_records")}
    for name in ("schedule_key", "error_summary", "completed_at", "started_at", "backup_status", "backup_source"):
        if name in existing_columns:
            op.drop_column("eisa_archive_records", name)
