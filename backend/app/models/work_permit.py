"""Permit-to-work records isolated from existing risk and incident models."""
from __future__ import annotations

from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class WorkPermit(Base):
    __tablename__ = "work_permits"
    __table_args__ = (UniqueConstraint("company_id", "client_reference", name="uq_work_permit_company_client_reference"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    permit_no: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    permit_type: Mapped[str] = mapped_column(String(40), index=True)
    description: Mapped[str] = mapped_column(Text)
    location: Mapped[str] = mapped_column(String(300))
    valid_from: Mapped[datetime] = mapped_column(DateTime, index=True)
    valid_until: Mapped[datetime] = mapped_column(DateTime, index=True)
    status: Mapped[str] = mapped_column(String(30), default="draft", index=True)
    opening_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    opening_checked_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    closed_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    cancelled_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    cancellation_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_id: Mapped[int | None] = mapped_column(ForeignKey("risk_assessments.id", ondelete="SET NULL"), nullable=True, index=True)
    incident_id: Mapped[int | None] = mapped_column(ForeignKey("incident_events.id", ondelete="SET NULL"), nullable=True, index=True)
    dof_id: Mapped[int | None] = mapped_column(ForeignKey("risk_dofs.id", ondelete="SET NULL"), nullable=True, index=True)
    field_inspection_id: Mapped[int | None] = mapped_column(ForeignKey("field_inspections.id", ondelete="SET NULL"), nullable=True, index=True)
    contractor_id: Mapped[int | None] = mapped_column(ForeignKey("contractor_companies.id", ondelete="SET NULL"), nullable=True, index=True)
    client_reference: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    approved_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    approvers: Mapped[list["WorkPermitApprover"]] = relationship(cascade="all, delete-orphan", order_by="WorkPermitApprover.step_order")


class WorkPermitEmployee(Base):
    __tablename__ = "work_permit_employees"
    __table_args__ = (UniqueConstraint("permit_id", "employee_id", name="uq_work_permit_employee"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    permit_id: Mapped[int] = mapped_column(ForeignKey("work_permits.id", ondelete="CASCADE"), index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id", ondelete="RESTRICT"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class WorkPermitControl(Base):
    __tablename__ = "work_permit_controls"
    __table_args__ = (UniqueConstraint("permit_id", "control_type", name="uq_work_permit_control_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    permit_id: Mapped[int] = mapped_column(ForeignKey("work_permits.id", ondelete="CASCADE"), index=True)
    control_type: Mapped[str] = mapped_column(String(50), index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    measured_value: Mapped[str | None] = mapped_column(String(80), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    checked_by_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WorkPermitApprover(Base):
    __tablename__ = "work_permit_approvers"
    __table_args__ = (UniqueConstraint("permit_id", "step_order", name="uq_work_permit_approver_step"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    permit_id: Mapped[int] = mapped_column(ForeignKey("work_permits.id", ondelete="CASCADE"), index=True)
    approver_user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), index=True)
    step_order: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
