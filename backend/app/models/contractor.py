"""Contractor records are separate from employees and users."""
from __future__ import annotations

from datetime import date, datetime
from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class ContractorCompany(Base):
    __tablename__ = "contractor_companies"
    __table_args__ = (UniqueConstraint("company_id", "name", name="uq_contractor_company_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(220), index=True)
    contract_number: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contract_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    contract_end: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    contact_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    workers: Mapped[list["ContractorWorker"]] = relationship(cascade="all, delete-orphan")
    documents: Mapped[list["ContractorDocument"]] = relationship(cascade="all, delete-orphan")


class ContractorWorker(Base):
    __tablename__ = "contractor_workers"
    __table_args__ = (UniqueConstraint("contractor_id", "full_name", name="uq_contractor_worker_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    contractor_id: Mapped[int] = mapped_column(ForeignKey("contractor_companies.id", ondelete="CASCADE"), index=True)
    full_name: Mapped[str] = mapped_column(String(160), index=True)
    national_id_masked: Mapped[str | None] = mapped_column(String(20), nullable=True)
    job_title: Mapped[str | None] = mapped_column(String(120), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)


class ContractorDocument(Base):
    __tablename__ = "contractor_documents"

    id: Mapped[int] = mapped_column(primary_key=True)
    contractor_id: Mapped[int] = mapped_column(ForeignKey("contractor_companies.id", ondelete="CASCADE"), index=True)
    document_type: Mapped[str] = mapped_column(String(60), index=True)
    title: Mapped[str] = mapped_column(String(220))
    file_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    document_record_id: Mapped[int | None] = mapped_column(ForeignKey("document_records.id"), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
