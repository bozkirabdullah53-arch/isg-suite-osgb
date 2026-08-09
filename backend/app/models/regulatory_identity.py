"""Isolated identity vault for formal authority integrations.

The ordinary Employee model remains untouched.  Full national/foreign identity
numbers needed by an authority profile belong here, encrypted at application
level, with only a masked representation and HMAC lookup digest outside the
ciphertext.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class RegulatoryIdentity(Base):
    __tablename__ = "regulatory_identities"
    __table_args__ = (
        UniqueConstraint("employee_id", "identity_type", name="uq_regulatory_identity_employee_type"),
        UniqueConstraint("company_id", "identity_type", "lookup_hash", name="uq_regulatory_identity_company_lookup"),
        Index("ix_regulatory_identity_company", "company_id"),
        Index("ix_regulatory_identity_employee", "employee_id"),
        Index("ix_regulatory_identity_lookup", "lookup_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(
        ForeignKey("companies.id", ondelete="RESTRICT"), nullable=False
    )
    employee_id: Mapped[int] = mapped_column(
        ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
    )
    identity_type: Mapped[str] = mapped_column(String(20), nullable=False, default="tckn")
    masked_value: Mapped[str] = mapped_column(String(32), nullable=False)
    ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    lookup_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    encryption_version: Mapped[str] = mapped_column(String(24), nullable=False, default="rid:v1")
    verified_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow
    )
