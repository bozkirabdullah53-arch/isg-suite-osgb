"""Add isolated Basic Occupational Health and Safety remote video training.

The migration is additive.  Existing training, examination, certificate,
employee and company tables are not altered.  Every new operational table has
company_id so the same tenant/RLS boundary can be applied independently.

Revision ID: 0089_remote_ohs_video
Revises: 0088_hazop_structured_data
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "0089_remote_ohs_video"
down_revision: Union[str, None] = "0088_hazop_structured_data"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enable_company_rls(table: str) -> None:
    if op.get_bind().dialect.name != "postgresql":
        return
    policy = f"{table}_company_scope"
    unset = "COALESCE(current_setting('app.current_user_id', true), '') = ''"
    bypass = "COALESCE(current_setting('app.rls_bypass', true), '') = '1'"
    allowed = (
        "string_to_array("
        "COALESCE(NULLIF(current_setting('app.allowed_company_ids', true), ''), '-1'), ','"
        ")::integer[]"
    )
    scope = f"({unset}) OR ({bypass}) OR (company_id = ANY ({allowed}))"
    op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY'))
    op.execute(sa.text(f'DROP POLICY IF EXISTS "{policy}" ON "{table}"'))
    op.execute(
        sa.text(
            f'CREATE POLICY "{policy}" ON "{table}" '
            f"FOR ALL USING ({scope}) WITH CHECK ({scope})"
        )
    )


def _drop_company_rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            sa.text(
                f'DROP POLICY IF EXISTS "{table}_company_scope" ON "{table}"'
            )
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("remote_training_programs"):
        op.create_table(
            "remote_training_programs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id", ondelete="SET NULL")),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="SET NULL")),
            sa.Column("title", sa.String(220), nullable=False, server_default="Basic Occupational Health and Safety Training"),
            sa.Column("training_type", sa.String(120), nullable=False, server_default="Basic Occupational Health and Safety Training"),
            sa.Column("description", sa.Text()),
            sa.Column("learning_objectives", sa.Text()),
            sa.Column("instructor_name", sa.String(180)),
            sa.Column("instructor_qualification", sa.String(220)),
            sa.Column("total_duration_seconds", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("completion_threshold_percent", sa.Integer(), nullable=False, server_default="90"),
            sa.Column("passing_score", sa.Integer(), nullable=False, server_default="60"),
            sa.Column("attempt_limit", sa.Integer(), nullable=False, server_default="3"),
            sa.Column("requires_final_exam", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
            sa.Column("revision_no", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("published_at", sa.DateTime()),
            sa.Column("archived_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_table(
            "remote_training_sections",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id", ondelete="SET NULL")),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("program_id", sa.Integer(), sa.ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("title", sa.String(220), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("learning_objectives", sa.Text()),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("status", sa.String(24), nullable=False, server_default="active"),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("program_id", "order_index", name="uq_remote_section_program_order"),
        )
        op.create_table(
            "remote_training_videos",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id", ondelete="SET NULL")),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("program_id", sa.Integer(), sa.ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("section_id", sa.Integer(), sa.ForeignKey("remote_training_sections.id", ondelete="CASCADE"), nullable=False),
            sa.Column("revision_of_id", sa.Integer(), sa.ForeignKey("remote_training_videos.id", ondelete="SET NULL")),
            sa.Column("title", sa.String(220), nullable=False),
            sa.Column("description", sa.Text()),
            sa.Column("learning_objectives", sa.Text()),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("revision_no", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("status", sa.String(32), nullable=False, server_default="uploading"),
            sa.Column("original_file_name", sa.String(255), nullable=False),
            sa.Column("content_type", sa.String(120), nullable=False),
            sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("duration_seconds", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("width", sa.Integer()),
            sa.Column("height", sa.Integer()),
            sa.Column("codec", sa.String(80)),
            sa.Column("storage_key", sa.String(700), nullable=False, unique=True),
            sa.Column("processing_job_id", sa.String(80)),
            sa.Column("processing_error", sa.String(1000)),
            sa.Column("published_at", sa.DateTime()),
            sa.Column("archived_at", sa.DateTime()),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_table(
            "remote_training_assets",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id", ondelete="SET NULL")),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("program_id", sa.Integer(), sa.ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("video_id", sa.Integer(), sa.ForeignKey("remote_training_videos.id", ondelete="CASCADE")),
            sa.Column("asset_type", sa.String(32), nullable=False),
            sa.Column("original_file_name", sa.String(255), nullable=False),
            sa.Column("content_type", sa.String(120), nullable=False),
            sa.Column("file_size_bytes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("storage_key", sa.String(700), nullable=False, unique=True),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_table(
            "remote_training_assignments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id", ondelete="SET NULL")),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="SET NULL")),
            sa.Column("program_id", sa.Integer(), sa.ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("workplace_name_snapshot", sa.String(220)),
            sa.Column("sgk_registration_number_snapshot", sa.String(40)),
            sa.Column("nace_code_snapshot", sa.String(20)),
            sa.Column("nace_description_snapshot", sa.String(500)),
            sa.Column("hazard_class_snapshot", sa.String(40)),
            sa.Column("employee_name_snapshot", sa.String(160), nullable=False),
            sa.Column("status", sa.String(24), nullable=False, server_default="not_started"),
            sa.Column("due_date", sa.Date()),
            sa.Column("assigned_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("assigned_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("started_at", sa.DateTime()),
            sa.Column("completed_at", sa.DateTime()),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("program_id", "employee_id", name="uq_remote_assignment_program_employee"),
        )
        op.create_table(
            "remote_training_video_progress",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("program_id", sa.Integer(), sa.ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("remote_training_assignments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("section_id", sa.Integer(), sa.ForeignKey("remote_training_sections.id", ondelete="CASCADE"), nullable=False),
            sa.Column("video_id", sa.Integer(), sa.ForeignKey("remote_training_videos.id", ondelete="CASCADE"), nullable=False),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("last_position_seconds", sa.Numeric(12, 3), nullable=False, server_default="0"),
            sa.Column("watched_duration_seconds", sa.Numeric(12, 3), nullable=False, server_default="0"),
            sa.Column("watched_percentage", sa.Numeric(6, 3), nullable=False, server_default="0"),
            sa.Column("status", sa.String(24), nullable=False, server_default="not_started"),
            sa.Column("viewing_sessions", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("started_at", sa.DateTime()),
            sa.Column("last_access_at", sa.DateTime()),
            sa.Column("completed_at", sa.DateTime()),
            sa.Column("device_info", sa.String(500)),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("assignment_id", "video_id", name="uq_remote_progress_assignment_video"),
        )
        op.create_table(
            "remote_training_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("program_id", sa.Integer(), sa.ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("remote_training_assignments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("video_id", sa.Integer(), sa.ForeignKey("remote_training_videos.id", ondelete="SET NULL")),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("event_type", sa.String(40), nullable=False),
            sa.Column("position_seconds", sa.Numeric(12, 3)),
            sa.Column("watched_seconds", sa.Numeric(12, 3)),
            sa.Column("device_info", sa.String(500)),
            sa.Column("ip_address", sa.String(64)),
            sa.Column("user_agent", sa.String(500)),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_table(
            "remote_training_questions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id", ondelete="SET NULL")),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("program_id", sa.Integer(), sa.ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("section_id", sa.Integer(), sa.ForeignKey("remote_training_sections.id", ondelete="SET NULL")),
            sa.Column("video_id", sa.Integer(), sa.ForeignKey("remote_training_videos.id", ondelete="SET NULL")),
            sa.Column("question_text", sa.Text(), nullable=False),
            sa.Column("options_json", sa.Text(), nullable=False),
            sa.Column("correct_option", sa.String(1), nullable=False),
            sa.Column("explanation", sa.Text()),
            sa.Column("timestamp_seconds", sa.Integer()),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_table(
            "remote_training_checkpoint_answers",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("program_id", sa.Integer(), sa.ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("remote_training_assignments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("question_id", sa.Integer(), sa.ForeignKey("remote_training_questions.id", ondelete="CASCADE"), nullable=False),
            sa.Column("answer", sa.String(1), nullable=False),
            sa.Column("is_correct", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("attempt_no", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("answered_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )
        op.create_table(
            "remote_training_program_questions",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("program_id", sa.Integer(), sa.ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("question_id", sa.Integer(), sa.ForeignKey("training_questions.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("position", sa.Integer(), nullable=False),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("program_id", "question_id", name="uq_remote_program_question"),
            sa.UniqueConstraint("program_id", "position", name="uq_remote_program_question_position"),
        )
        op.create_table(
            "remote_training_exam_attempts",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("program_id", sa.Integer(), sa.ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("remote_training_assignments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("attempt_no", sa.Integer(), nullable=False),
            sa.Column("question_ids_json", sa.Text(), nullable=False),
            sa.Column("answers_json", sa.Text(), nullable=False),
            sa.Column("score", sa.Integer()),
            sa.Column("passed", sa.Boolean(), index=True),
            sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("submitted_at", sa.DateTime()),
            sa.Column("submitted_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.UniqueConstraint("assignment_id", "attempt_no", name="uq_remote_exam_assignment_attempt"),
        )
        op.create_table(
            "remote_training_certificates",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("program_id", sa.Integer(), sa.ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("assignment_id", sa.Integer(), sa.ForeignKey("remote_training_assignments.id", ondelete="CASCADE"), nullable=False),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False),
            sa.Column("employee_name_snapshot", sa.String(160), nullable=False),
            sa.Column("company_name_snapshot", sa.String(220), nullable=False),
            sa.Column("workplace_name_snapshot", sa.String(220)),
            sa.Column("sgk_registration_number_snapshot", sa.String(40)),
            sa.Column("nace_code_snapshot", sa.String(20)),
            sa.Column("nace_description_snapshot", sa.String(500)),
            sa.Column("hazard_class_snapshot", sa.String(40)),
            sa.Column("training_name", sa.String(220), nullable=False),
            sa.Column("training_type", sa.String(120), nullable=False, server_default="Basic Occupational Health and Safety Training"),
            sa.Column("training_duration_seconds", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("training_date", sa.Date(), nullable=False),
            sa.Column("instructor_name_snapshot", sa.String(180)),
            sa.Column("examination_score", sa.Integer()),
            sa.Column("certificate_number", sa.String(64), nullable=False, unique=True),
            sa.Column("verification_code", sa.String(80), nullable=False, unique=True),
            sa.Column("revision_no", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("issue_date", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("assignment_id", name="uq_remote_certificate_assignment"),
        )
        op.create_table(
            "remote_training_employee_access",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("osgb_id", sa.Integer(), sa.ForeignKey("osgb_organizations.id", ondelete="SET NULL")),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
            sa.UniqueConstraint("user_id", name="uq_remote_employee_access_user"),
            sa.UniqueConstraint("employee_id", name="uq_remote_employee_access_employee"),
        )
        op.create_table(
            "remote_training_audit_logs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
            sa.Column("action", sa.String(80), nullable=False),
            sa.Column("entity_type", sa.String(80), nullable=False),
            sa.Column("entity_id", sa.String(80)),
            sa.Column("details_json", sa.Text()),
            sa.Column("ip_address", sa.String(64)),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        )

    indexes = {
        "remote_training_programs": (
            ("ix_remote_training_programs_osgb", ["osgb_id"]),
            ("ix_remote_training_programs_company", ["company_id"]),
            ("ix_remote_training_programs_branch", ["branch_id"]),
            ("ix_remote_training_programs_status", ["status"]),
            ("ix_remote_training_programs_company_status", ["company_id", "status"]),
            ("ix_remote_training_programs_created_at", ["created_at"]),
        ),
        "remote_training_sections": (
            ("ix_remote_training_sections_osgb", ["osgb_id"]),
            ("ix_remote_training_sections_company", ["company_id"]),
            ("ix_remote_training_sections_program", ["program_id"]),
        ),
        "remote_training_videos": (
            ("ix_remote_training_videos_osgb", ["osgb_id"]),
            ("ix_remote_training_videos_company", ["company_id"]),
            ("ix_remote_training_videos_program", ["program_id"]),
            ("ix_remote_training_videos_section", ["section_id"]),
            ("ix_remote_training_videos_revision_of", ["revision_of_id"]),
            ("ix_remote_training_videos_status", ["status"]),
            ("ix_remote_training_videos_created_by", ["created_by_id"]),
            ("ix_remote_training_videos_created_at", ["created_at"]),
            ("ix_remote_training_videos_program_status", ["program_id", "status"]),
            ("ix_remote_training_videos_section_order", ["section_id", "order_index"]),
            ("ix_remote_training_videos_current", ["program_id", "is_current"]),
            ("ix_remote_training_videos_processing_job", ["processing_job_id"]),
        ),
        "remote_training_assets": (
            ("ix_remote_training_assets_osgb", ["osgb_id"]),
            ("ix_remote_training_assets_company", ["company_id"]),
            ("ix_remote_training_assets_program", ["program_id"]),
            ("ix_remote_training_assets_video", ["video_id"]),
            ("ix_remote_training_assets_video_type", ["video_id", "asset_type"]),
        ),
        "remote_training_assignments": (
            ("ix_remote_training_assignments_osgb", ["osgb_id"]),
            ("ix_remote_training_assignments_company", ["company_id"]),
            ("ix_remote_training_assignments_branch", ["branch_id"]),
            ("ix_remote_training_assignments_program", ["program_id"]),
            ("ix_remote_training_assignments_employee", ["employee_id"]),
            ("ix_remote_training_assignments_status", ["status"]),
            ("ix_remote_training_assignments_due_date", ["due_date"]),
            ("ix_remote_training_assignments_company_status", ["company_id", "status"]),
            ("ix_remote_training_assignments_assigned_at", ["assigned_at"]),
        ),
        "remote_training_video_progress": (
            ("ix_remote_progress_company", ["company_id"]),
            ("ix_remote_progress_program", ["program_id"]),
            ("ix_remote_progress_assignment", ["assignment_id"]),
            ("ix_remote_progress_section", ["section_id"]),
            ("ix_remote_progress_video", ["video_id"]),
            ("ix_remote_progress_employee", ["employee_id"]),
            ("ix_remote_progress_status", ["status"]),
            ("ix_remote_progress_company_status", ["company_id", "status"]),
        ),
        "remote_training_events": (
            ("ix_remote_training_events_company", ["company_id"]),
            ("ix_remote_training_events_program", ["program_id"]),
            ("ix_remote_training_events_assignment", ["assignment_id"]),
            ("ix_remote_training_events_employee", ["employee_id"]),
            ("ix_remote_training_events_video", ["video_id"]),
            ("ix_remote_training_events_user", ["user_id"]),
            ("ix_remote_training_events_created", ["created_at"]),
            ("ix_remote_training_events_company_created", ["company_id", "created_at"]),
        ),
        "remote_training_questions": (
            ("ix_remote_training_questions_osgb", ["osgb_id"]),
            ("ix_remote_training_questions_company", ["company_id"]),
            ("ix_remote_training_questions_program", ["program_id"]),
            ("ix_remote_training_questions_section", ["section_id"]),
            ("ix_remote_training_questions_video", ["video_id"]),
        ),
        "remote_training_checkpoint_answers": (
            ("ix_remote_checkpoint_answers_company", ["company_id"]),
            ("ix_remote_checkpoint_answers_program", ["program_id"]),
            ("ix_remote_checkpoint_answers_assignment", ["assignment_id"]),
            ("ix_remote_checkpoint_answers_employee", ["employee_id"]),
            ("ix_remote_checkpoint_answers_question", ["question_id"]),
            ("ix_remote_checkpoint_answers_answered", ["answered_at"]),
        ),
        "remote_training_program_questions": (
            ("ix_remote_program_questions_company", ["company_id"]),
            ("ix_remote_program_questions_program", ["program_id"]),
            ("ix_remote_program_questions_question", ["question_id"]),
        ),
        "remote_training_exam_attempts": (
            ("ix_remote_exam_attempts_company", ["company_id"]),
            ("ix_remote_exam_attempts_program", ["program_id"]),
            ("ix_remote_exam_attempts_assignment", ["assignment_id"]),
            ("ix_remote_exam_attempts_employee", ["employee_id"]),
            ("ix_remote_exam_attempts_passed", ["passed"]),
            ("ix_remote_exam_attempts_company_status", ["company_id", "passed"]),
        ),
        "remote_training_certificates": (
            ("ix_remote_certificates_company", ["company_id"]),
            ("ix_remote_certificates_program", ["program_id"]),
            ("ix_remote_certificates_assignment", ["assignment_id"]),
            ("ix_remote_certificates_employee", ["employee_id"]),
            ("ix_remote_certificates_issue_date", ["issue_date"]),
        ),
        "remote_training_employee_access": (
            ("ix_remote_employee_access_osgb", ["osgb_id"]),
            ("ix_remote_employee_access_company", ["company_id"]),
            ("ix_remote_employee_access_user", ["user_id"]),
            ("ix_remote_employee_access_employee", ["employee_id"]),
            ("ix_remote_employee_access_active", ["is_active"]),
        ),
        "remote_training_audit_logs": (
            ("ix_remote_training_audit_company", ["company_id"]),
            ("ix_remote_training_audit_user", ["user_id"]),
            ("ix_remote_training_audit_action", ["action"]),
            ("ix_remote_training_audit_entity", ["entity_type", "entity_id"]),
            ("ix_remote_training_audit_created", ["created_at"]),
            ("ix_remote_training_audit_company_created", ["company_id", "created_at"]),
        ),
    }
    for table, table_indexes in indexes.items():
        existing = {item["name"] for item in sa.inspect(bind).get_indexes(table)}
        for name, columns in table_indexes:
            if name not in existing:
                op.create_index(name, table, columns)

    for table in indexes:
        _enable_company_rls(table)


def downgrade() -> None:
    tables = (
        "remote_training_audit_logs",
        "remote_training_employee_access",
        "remote_training_certificates",
        "remote_training_exam_attempts",
        "remote_training_program_questions",
        "remote_training_checkpoint_answers",
        "remote_training_questions",
        "remote_training_events",
        "remote_training_video_progress",
        "remote_training_assignments",
        "remote_training_assets",
        "remote_training_videos",
        "remote_training_sections",
        "remote_training_programs",
    )
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in tables:
        if inspector.has_table(table):
            _drop_company_rls(table)
            op.drop_table(table)
