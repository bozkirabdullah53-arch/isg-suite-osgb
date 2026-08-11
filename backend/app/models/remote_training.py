"""Isolated models for the Basic Occupational Health and Safety remote course.

The existing training, examination, certificate and employee tables are kept
unchanged.  These tables are an additive content/attendance layer and carry
their own company scope so that PostgreSQL RLS and the application access
checks can be applied independently.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


REMOTE_TRAINING_TYPE = "Basic Occupational Health and Safety Training"

PROGRAM_STATUSES = ("draft", "ready_for_review", "published", "unpublished", "archived")
VIDEO_STATUSES = (
    "draft",
    "uploading",
    "processing",
    "processing_failed",
    "ready_for_review",
    "published",
    "unpublished",
    "archived",
)
ASSIGNMENT_STATUSES = ("not_started", "in_progress", "completed", "failed", "expired")
PROGRESS_STATUSES = ("not_started", "in_progress", "completed")
ASSET_TYPES = ("thumbnail", "subtitle", "supporting_document")


class RemoteTrainingProgram(Base):
    __tablename__ = "remote_training_programs"
    __table_args__ = (
        Index("ix_remote_training_programs_company_status", "company_id", "status"),
        Index("ix_remote_training_programs_branch", "branch_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int | None] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[int | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(
        String(220), default="Basic Occupational Health and Safety Training"
    )
    training_type: Mapped[str] = mapped_column(
        String(120), default=REMOTE_TRAINING_TYPE, nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    learning_objectives: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructor_name: Mapped[str | None] = mapped_column(String(180), nullable=True)
    instructor_qualification: Mapped[str | None] = mapped_column(String(220), nullable=True)
    total_duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completion_threshold_percent: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    passing_score: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    attempt_limit: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    requires_final_exam: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="draft", index=True)
    revision_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RemoteTrainingSection(Base):
    __tablename__ = "remote_training_sections"
    __table_args__ = (
        UniqueConstraint("program_id", "order_index", name="uq_remote_section_program_order"),
        Index("ix_remote_training_sections_program", "program_id"),
        Index("ix_remote_training_sections_company", "company_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int | None] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    learning_objectives: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RemoteTrainingVideo(Base):
    __tablename__ = "remote_training_videos"
    __table_args__ = (
        Index("ix_remote_training_videos_program_status", "program_id", "status"),
        Index("ix_remote_training_videos_section_order", "section_id", "order_index"),
        Index("ix_remote_training_videos_company", "company_id"),
        Index("ix_remote_training_videos_current", "program_id", "is_current"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int | None] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_sections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    revision_of_id: Mapped[int | None] = mapped_column(
        ForeignKey("remote_training_videos.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(220), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    learning_objectives: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="uploading", index=True)
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    codec: Mapped[str | None] = mapped_column(String(80), nullable=True)
    storage_key: Mapped[str] = mapped_column(String(700), nullable=False, unique=True)
    processing_job_id: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    processing_error: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RemoteTrainingAsset(Base):
    __tablename__ = "remote_training_assets"
    __table_args__ = (
        Index("ix_remote_training_assets_video_type", "video_id", "asset_type"),
        Index("ix_remote_training_assets_company", "company_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int | None] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    video_id: Mapped[int | None] = mapped_column(
        ForeignKey("remote_training_videos.id", ondelete="CASCADE"), nullable=True, index=True
    )
    asset_type: Mapped[str] = mapped_column(String(32), nullable=False)
    original_file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(700), nullable=False, unique=True)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class RemoteTrainingAssignment(Base):
    __tablename__ = "remote_training_assignments"
    __table_args__ = (
        UniqueConstraint("program_id", "employee_id", name="uq_remote_assignment_program_employee"),
        Index("ix_remote_training_assignments_company_status", "company_id", "status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int | None] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    branch_id: Mapped[int | None] = mapped_column(
        ForeignKey("branches.id", ondelete="SET NULL"), nullable=True, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    workplace_name_snapshot: Mapped[str | None] = mapped_column(String(220), nullable=True)
    sgk_registration_number_snapshot: Mapped[str | None] = mapped_column(String(40), nullable=True)
    nace_code_snapshot: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nace_description_snapshot: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hazard_class_snapshot: Mapped[str | None] = mapped_column(String(40), nullable=True)
    employee_name_snapshot: Mapped[str] = mapped_column(String(160), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="not_started", index=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    assigned_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RemoteTrainingVideoProgress(Base):
    __tablename__ = "remote_training_video_progress"
    __table_args__ = (
        UniqueConstraint("assignment_id", "video_id", name="uq_remote_progress_assignment_video"),
        Index("ix_remote_progress_company_status", "company_id", "status"),
        Index("ix_remote_progress_employee", "employee_id"),
        Index("ix_remote_progress_program", "program_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_sections.id", ondelete="CASCADE"), nullable=False, index=True
    )
    video_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_videos.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    last_position_seconds: Mapped[float] = mapped_column(Numeric(12, 3), default=0, nullable=False)
    watched_duration_seconds: Mapped[float] = mapped_column(Numeric(12, 3), default=0, nullable=False)
    watched_percentage: Mapped[float] = mapped_column(Numeric(6, 3), default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="not_started", index=True)
    viewing_sessions: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_access_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    device_info: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RemoteTrainingEvent(Base):
    __tablename__ = "remote_training_events"
    __table_args__ = (
        Index("ix_remote_training_events_company_created", "company_id", "created_at"),
        Index("ix_remote_training_events_assignment", "assignment_id"),
        Index("ix_remote_training_events_video", "video_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    video_id: Mapped[int | None] = mapped_column(
        ForeignKey("remote_training_videos.id", ondelete="SET NULL"), nullable=True, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False)
    position_seconds: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    watched_seconds: Mapped[float | None] = mapped_column(Numeric(12, 3), nullable=True)
    device_info: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class RemoteTrainingQuestion(Base):
    __tablename__ = "remote_training_questions"
    __table_args__ = (
        Index("ix_remote_training_questions_program", "program_id"),
        Index("ix_remote_training_questions_video", "video_id"),
        Index("ix_remote_training_questions_company", "company_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int | None] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    section_id: Mapped[int | None] = mapped_column(
        ForeignKey("remote_training_sections.id", ondelete="SET NULL"), nullable=True, index=True
    )
    video_id: Mapped[int | None] = mapped_column(
        ForeignKey("remote_training_videos.id", ondelete="SET NULL"), nullable=True, index=True
    )
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    options_json: Mapped[str] = mapped_column(Text, nullable=False)
    correct_option: Mapped[str] = mapped_column(String(1), nullable=False)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    timestamp_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RemoteTrainingCheckpointAnswer(Base):
    __tablename__ = "remote_training_checkpoint_answers"
    __table_args__ = (
        Index("ix_remote_checkpoint_answers_assignment", "assignment_id"),
        Index("ix_remote_checkpoint_answers_company", "company_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    answer: Mapped[str] = mapped_column(String(1), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attempt_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    answered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)


class RemoteTrainingProgramQuestion(Base):
    __tablename__ = "remote_training_program_questions"
    __table_args__ = (
        UniqueConstraint("program_id", "question_id", name="uq_remote_program_question"),
        UniqueConstraint("program_id", "position", name="uq_remote_program_question_position"),
        Index("ix_remote_program_questions_company", "company_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[int] = mapped_column(
        ForeignKey("training_questions.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RemoteTrainingExamAttempt(Base):
    __tablename__ = "remote_training_exam_attempts"
    __table_args__ = (
        UniqueConstraint("assignment_id", "attempt_no", name="uq_remote_exam_assignment_attempt"),
        Index("ix_remote_exam_attempts_company_status", "company_id", "passed"),
        Index("ix_remote_exam_attempts_assignment", "assignment_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    question_ids_json: Mapped[str] = mapped_column(Text, nullable=False)
    answers_json: Mapped[str] = mapped_column(Text, nullable=False)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    passed: Mapped[bool | None] = mapped_column(Boolean, nullable=True, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    submitted_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class RemoteTrainingCertificate(Base):
    __tablename__ = "remote_training_certificates"
    __table_args__ = (
        UniqueConstraint("assignment_id", name="uq_remote_certificate_assignment"),
        UniqueConstraint("certificate_number", name="uq_remote_certificate_number"),
        UniqueConstraint("verification_code", name="uq_remote_certificate_verification"),
        Index("ix_remote_certificates_company", "company_id"),
        Index("ix_remote_certificates_employee", "employee_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    program_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assignment_id: Mapped[int] = mapped_column(
        ForeignKey("remote_training_assignments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    employee_name_snapshot: Mapped[str] = mapped_column(String(160), nullable=False)
    company_name_snapshot: Mapped[str] = mapped_column(String(220), nullable=False)
    workplace_name_snapshot: Mapped[str | None] = mapped_column(String(220), nullable=True)
    sgk_registration_number_snapshot: Mapped[str | None] = mapped_column(String(40), nullable=True)
    nace_code_snapshot: Mapped[str | None] = mapped_column(String(20), nullable=True)
    nace_description_snapshot: Mapped[str | None] = mapped_column(String(500), nullable=True)
    hazard_class_snapshot: Mapped[str | None] = mapped_column(String(40), nullable=True)
    training_name: Mapped[str] = mapped_column(String(220), nullable=False)
    training_type: Mapped[str] = mapped_column(String(120), default=REMOTE_TRAINING_TYPE)
    training_duration_seconds: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    training_date: Mapped[date] = mapped_column(Date, nullable=False)
    instructor_name_snapshot: Mapped[str | None] = mapped_column(String(180), nullable=True)
    examination_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    certificate_number: Mapped[str] = mapped_column(String(64), nullable=False)
    verification_code: Mapped[str] = mapped_column(String(80), nullable=False)
    revision_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    issue_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class RemoteTrainingEmployeeAccess(Base):
    __tablename__ = "remote_training_employee_access"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_remote_employee_access_user"),
        UniqueConstraint("employee_id", name="uq_remote_employee_access_employee"),
        Index("ix_remote_employee_access_company", "company_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    osgb_id: Mapped[int | None] = mapped_column(
        ForeignKey("osgb_organizations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )


class RemoteTrainingAuditLog(Base):
    __tablename__ = "remote_training_audit_logs"
    __table_args__ = (
        Index("ix_remote_training_audit_company_created", "company_id", "created_at"),
        Index("ix_remote_training_audit_entity", "entity_type", "entity_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
