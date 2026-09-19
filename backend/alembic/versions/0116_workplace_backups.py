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
    op.add_column("eisa_archive_records", sa.Column("backup_source", sa.String(20), nullable=False, server_default="manual"))
    op.add_column("eisa_archive_records", sa.Column("backup_status", sa.String(20), nullable=False, server_default="completed"))
    op.add_column("eisa_archive_records", sa.Column("started_at", sa.DateTime(), nullable=True))
    op.add_column("eisa_archive_records", sa.Column("completed_at", sa.DateTime(), nullable=True))
    op.add_column("eisa_archive_records", sa.Column("error_summary", sa.String(1000), nullable=True))
    op.add_column("eisa_archive_records", sa.Column("schedule_key", sa.String(120), nullable=True))
    op.create_unique_constraint("uq_eisa_archive_records_schedule_key", "eisa_archive_records", ["schedule_key"])

def downgrade():
    op.drop_constraint("uq_eisa_archive_records_schedule_key", "eisa_archive_records", type_="unique")
    for name in ("schedule_key", "error_summary", "completed_at", "started_at", "backup_status", "backup_source"):
        op.drop_column("eisa_archive_records", name)
