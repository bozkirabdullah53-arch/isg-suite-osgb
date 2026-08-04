"""e-Reçete çekirdek tabloları

Revision ID: 0073_erecete_core
Revises: 0072_ibys_nonconformity_dof
"""
from alembic import op
import sqlalchemy as sa

revision = "0073_erecete_core"
down_revision = "0072_ibys_nonconformity_dof"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    return name in sa.inspect(op.get_bind()).get_table_names()


def _ensure_index(table_name: str, index_name: str, columns: list[str]) -> None:
    indexes = {item["name"] for item in sa.inspect(op.get_bind()).get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns)


def upgrade():
    if not _table_exists("prescriptions"):
        op.create_table(
            "prescriptions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id"), nullable=False),
            sa.Column("health_record_id", sa.Integer(), sa.ForeignKey("health_records.id"), nullable=True),
            sa.Column("physician_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="draft"),
            sa.Column("prescription_date", sa.Date(), nullable=False),
            sa.Column("diagnosis_code", sa.String(length=32), nullable=True),
            sa.Column("diagnosis_text", sa.Text(), nullable=True),
            sa.Column("clinical_note", sa.Text(), nullable=True),
            sa.Column("medula_prescription_no", sa.String(length=80), nullable=True, unique=True),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("cancelled_at", sa.DateTime(), nullable=True),
            sa.Column("cancel_reason", sa.Text(), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint("status in ('draft','ready','sending','approved','rejected','cancelled')", name="ck_prescriptions_status"),
        )
    for name, cols in [
        ("ix_prescriptions_company_id", ["company_id"]),
        ("ix_prescriptions_employee_id", ["employee_id"]),
        ("ix_prescriptions_health_record_id", ["health_record_id"]),
        ("ix_prescriptions_physician_user_id", ["physician_user_id"]),
        ("ix_prescriptions_status", ["status"]),
        ("ix_prescriptions_prescription_date", ["prescription_date"]),
    ]:
        _ensure_index("prescriptions", name, cols)

    if not _table_exists("prescription_items"):
        op.create_table(
            "prescription_items",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("prescription_id", sa.Integer(), sa.ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("medication_name", sa.String(length=240), nullable=False),
            sa.Column("medication_code", sa.String(length=80), nullable=True),
            sa.Column("dose", sa.String(length=120), nullable=False),
            sa.Column("frequency", sa.String(length=120), nullable=False),
            sa.Column("route", sa.String(length=80), nullable=True),
            sa.Column("duration", sa.String(length=120), nullable=True),
            sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("usage_instruction", sa.Text(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.CheckConstraint("quantity > 0", name="ck_prescription_items_quantity_positive"),
            sa.CheckConstraint("sort_order >= 0", name="ck_prescription_items_sort_order"),
        )
    _ensure_index("prescription_items", "ix_prescription_items_prescription_id", ["prescription_id"])

    if not _table_exists("prescription_submissions"):
        op.create_table(
            "prescription_submissions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("prescription_id", sa.Integer(), sa.ForeignKey("prescriptions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("provider", sa.String(length=40), nullable=False, server_default="medula"),
            sa.Column("status", sa.String(length=24), nullable=False, server_default="not_configured"),
            sa.Column("request_payload", sa.Text(), nullable=True),
            sa.Column("response_payload", sa.Text(), nullable=True),
            sa.Column("external_reference", sa.String(length=120), nullable=True),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
    _ensure_index("prescription_submissions", "ix_prescription_submissions_prescription_id", ["prescription_id"])
    _ensure_index("prescription_submissions", "ix_prescription_submissions_status", ["status"])

    if not _table_exists("prescription_submission_attempts"):
        op.create_table(
            "prescription_submission_attempts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("submission_id", sa.Integer(), sa.ForeignKey("prescription_submissions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("attempt_no", sa.Integer(), nullable=False),
            sa.Column("outcome", sa.String(length=32), nullable=False),
            sa.Column("http_status", sa.Integer(), nullable=True),
            sa.Column("error_code", sa.String(length=80), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
        )
    _ensure_index("prescription_submission_attempts", "ix_prescription_submission_attempts_submission_id", ["submission_id"])
    _ensure_index("prescription_submission_attempts", "ix_prescription_submission_attempts_outcome", ["outcome"])

    if not _table_exists("medula_error_logs"):
        op.create_table(
            "medula_error_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("prescription_id", sa.Integer(), sa.ForeignKey("prescriptions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("submission_id", sa.Integer(), sa.ForeignKey("prescription_submissions.id", ondelete="SET NULL"), nullable=True),
            sa.Column("error_code", sa.String(length=80), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=False),
            sa.Column("correlation_id", sa.String(length=120), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
    _ensure_index("medula_error_logs", "ix_medula_error_logs_prescription_id", ["prescription_id"])
    _ensure_index("medula_error_logs", "ix_medula_error_logs_submission_id", ["submission_id"])
    _ensure_index("medula_error_logs", "ix_medula_error_logs_error_code", ["error_code"])
    _ensure_index("medula_error_logs", "ix_medula_error_logs_correlation_id", ["correlation_id"])


def downgrade():
    op.drop_table("medula_error_logs")
    op.drop_table("prescription_submission_attempts")
    op.drop_table("prescription_submissions")
    op.drop_table("prescription_items")
    op.drop_table("prescriptions")
